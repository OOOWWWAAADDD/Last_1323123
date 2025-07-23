import streamlit as st
import google.generativeai as genai
import pandas as pd
import re

# --- 定数定義 ---
CSV_FILE_PATH = 'makeup_products.csv' # あなたのCSVファイル名

# --- データ読み込み ---
@st.cache_data
def load_and_process_makeup_data():
    """CSVデータを読み込み、整形してDataFrameを返す"""
    try:
        df = pd.read_csv(CSV_FILE_PATH, encoding='utf-8-sig')
        df['推奨パーソナルカラー'] = df['推奨パーソナルカラー'].apply(lambda x: [pc.strip() for pc in str(x).split(';')])
        df['価格'] = pd.to_numeric(df['価格'], errors='coerce')
        return df
    except FileNotFoundError:
        st.error(f"エラー: CSVファイル '{CSV_FILE_PATH}' が見つかりません。")
        st.stop()
    except Exception as e:
        st.error(f"CSVファイルの読み込み中にエラーが発生しました: {e}")
        st.stop()

# --- session_stateの初期化 ---
def initialize_session_state():
    """アプリで使うセッション変数を初期化する"""
    if 'suggestion_generated' not in st.session_state:
        st.session_state.suggestion_generated = False
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if 'user_info' not in st.session_state:
        st.session_state.user_info = {}
    if 'recommended_products' not in st.session_state:
        st.session_state.recommended_products = []
    if 'user_selections' not in st.session_state:
        st.session_state.user_selections = {}
    if 'diagnosis_step' not in st.session_state:
        st.session_state.diagnosis_step = 0
    if 'answers' not in st.session_state:
        st.session_state.answers = []

# --- 背景色を変更する関数 ---
def set_background_color(personal_color_jp):
    personal_color_map = {"イエベ春": "春", "イエベ秋": "秋", "ブルベ夏": "夏", "ブルベ冬": "冬"}
    color_map = {"春": "#FDF5E6", "夏": "#F0F8FF", "秋": "#FAFAD2", "冬": "#E6E6FA"}
    internal_color_key = personal_color_map.get(personal_color_jp)
    bg_color = color_map.get(internal_color_key, '#FFFFFF')
    background_style = f"<style>.stApp {{ background-color: {bg_color}; }}</style>"
    st.markdown(background_style, unsafe_allow_html=True)

# --- AIの応答から商品を抽出するヘルパー関数 ---
def parse_products_from_response(response_text, df):
    sections = re.split(r'### (ベースメイク|アイメイク|リップメイク|チーク)', response_text)
    all_products = []
    found_products = set()
    for i in range(1, len(sections), 2):
        category_name = sections[i]
        category_text = sections[i+1]
        pattern = r"\* \*\*商品名\*\*: (.*?),\s\*\*ブランド\*\*: (.*?),\s\*\*おすすめ理由\*\*: (.*?)(?=\n\*|$)"
        matches = re.findall(pattern, category_text, re.DOTALL)
        for product_name, brand_name, reason in matches:
            product_name, brand_name, reason = product_name.strip(), brand_name.strip(), reason.strip().replace('\n', ' ')
            result = df[(df['商品名'].str.strip() == product_name) & (df['ブランド名'].str.strip() == brand_name)]
            if not result.empty and (product_name, brand_name) not in found_products:
                product_info = result.iloc[0].to_dict()
                product_info['おすすめ理由'] = reason
                product_info['商品カテゴリ'] = 'アイシャドウ' if category_name == 'アイメイク' else category_name
                all_products.append(product_info)
                found_products.add((product_name, brand_name))
    return all_products

# --- サイドバーの描画 ---
def render_sidebar():
    with st.sidebar:
        st.title("🛒 あなたの選択リスト")
        selections = st.session_state.get('user_selections', {})
        if not selections:
            st.info("右の画面で商品を選択すると、ここにリストが表示されます。")
        else:
            total_price = sum(p.get('価格', 0) for p in selections.values())
            for category, product in selections.items():
                st.subheader(f"{product.get('商品カテゴリ', category)}")
                st.markdown(f"**{product.get('商品名')}**")
                st.text(f"{product.get('ブランド名')} / ¥{int(product.get('価格', 0)):,}")
                st.divider()
            st.header(f"合計金額: ¥{int(total_price):,}")
            user_budget = st.session_state.user_info.get('budget', 0)
            if user_budget > 0:
                st.progress(min(total_price / user_budget, 1.0)); st.caption(f"設定予算 ¥{user_budget:,} に対して")

# --- 左カラムの描画 ---
def render_left_column():
    st.header("1. あなたの情報を入力 ✍️")
    with st.container(border=True):
        with st.expander("🎨 4シーズン・パーソナルカラー診断はこちら"):
            questions = ["Q1. 瞳の色や印象は？", "Q2. 似合うアクセサリーは？", "Q3. 肌の質感は？", "Q4. 似合うリップの色は？"]
            options = [["A. 明るい茶色", "B. 深いこげ茶色", "C. ソフトな赤茶/黒", "D. はっきりした黒"], ["A. 明るいゴールド", "B. マットなゴールド", "C. 優しいシルバー", "D. 輝くシルバー"], ["A. ツヤ・薄め", "B. マット・厚め", "C. サラサラ・マット", "D. ハリがある"], ["A. コーラルピンク系", "B. テラコッタ系", "C. ローズピンク系", "D. チェリーレッド系"]]
            answer_to_season = {'A': '春', 'B': '秋', 'C': '夏', 'D': '冬'}
            if st.session_state.diagnosis_step > 0 and st.session_state.diagnosis_step <= len(questions):
                q_index = st.session_state.diagnosis_step - 1; st.write(f"**{questions[q_index]}**"); cols = st.columns(len(options[q_index]))
                for i, opt in enumerate(options[q_index]):
                    if cols[i].button(opt, key=f"q{q_index}{i}", use_container_width=True):
                        st.session_state.answers.append(list(answer_to_season.keys())[i]); st.session_state.diagnosis_step += 1; st.rerun()
            elif st.session_state.diagnosis_step > len(questions):
                scores = {'春': 0, '夏': 0, '秋': 0, '冬': 0};
                for ans in st.session_state.answers: scores[answer_to_season[ans]] += 1
                final_season_jp = max(scores, key=scores.get); final_season_map = {"春": "イエベ春", "秋": "イエベ秋", "夏": "ブルベ夏", "冬": "ブルベ冬"}
                st.info(f"診断結果: **{final_season_map[final_season_jp]}**"); st.session_state.user_info['personal_color'] = final_season_map[final_season_jp]
                if st.button("診断をリセット"): st.session_state.diagnosis_step = 0; st.session_state.answers = []; st.rerun()
            else:
                if st.button("診断を開始する", use_container_width=True): st.session_state.diagnosis_step = 1; st.rerun()
        
        pc_options = ["選択してください", "イエベ春", "イエベ秋", "ブルベ夏", "ブルベ冬"]
        pc_index = pc_options.index(st.session_state.user_info.get('personal_color', '選択してください'))
        personal_color = st.selectbox("パーソナルカラー", pc_options, index=pc_index)
        face_shape = st.selectbox("顔の形", ("丸顔", "面長", "卵型", "ベース型", "逆三角形"))
        budget = st.slider("💄 メイク用品の予算", 0, 30000, 15000, 1000, "¥%d")
        st.markdown("##### なりたいイメージ")
        cute_cool = st.slider("かわいい ↔ かっこいい", -5, 5, 0)
        fresh_mature = st.slider("フレッシュ ↔ 大人っぽい", -5, 5, 0)
        desired_impression_text = st.text_area("その他、具体的なイメージ (任意)", placeholder="例：上品で親しみやすい雰囲気。")
        if st.button("AIにスタイリングを相談する", type="primary", use_container_width=True):
            if personal_color == "選択してください": st.warning("パーソナルカラーを選択してください。")
            else:
                with st.spinner('AIがあなたにぴったりのスタイルを考えています...'):
                    st.session_state.user_info = {'personal_color': personal_color, 'face_shape': face_shape, 'budget': budget, 'cute_cool': cute_cool, 'fresh_mature': fresh_mature, 'free_text': desired_impression_text}
                    df = load_and_process_makeup_data()
                    first_prompt = f"""# 指示: あなたはプロのスタイリストです。以下のユーザー情報と商品リストに基づき、最適な「メイク」と「髪型」を提案してください。
# ユーザー情報: {st.session_state.user_info}
# 提案ルール: 
* 予算内で実現できる商品を提案してください。
* 各メイクカテゴリで、商品を**3つ**提案することを基本とします。適切な商品がない場合のみ、それ以下の数でも構いません。
* 提案は指定のMarkdownフォーマットに従ってください。
# 商品リスト: {df.to_string()}
## あなたへのトータルスタイリング提案 ✨
### ヘアスタイル
* **提案**: [具体的な髪型を提案]
* **理由**: [理由]
### ベースメイク
* **商品名**: [商品名], **ブランド**: [ブランド名], **おすすめ理由**: [理由]
(ここに商品を3つ提案)
### アイメイク
* **商品名**: [商品名], **ブランド**: [ブランド名], **おすすめ理由**: [理由]
(ここに商品を3つ提案)
### リップメイク
* **商品名**: [商品名], **ブランド**: [ブランド名], **おすすめ理由**: [理由]
(ここに商品を3つ提案)
### チーク
* **商品名**: [商品名], **ブランド**: [ブランド名], **おすすめ理由**: [理由]
(ここに商品を3つ提案)
"""
                    model = genai.GenerativeModel('gemini-1.5-flash'); response = model.generate_content(first_prompt)
                    st.session_state.recommended_products = parse_products_from_response(response.text, df)
                    st.session_state.suggestion_generated = True
                    st.session_state.user_selections = {}
                    st.rerun()

# --- 右カラムの描画 ---
def render_right_column():
    st.header("2. AIからの提案＆商品選択 💅")
    if not st.session_state.suggestion_generated:
        st.info("左のパネルであなたの情報を入力し、「AIに相談する」ボタンを押してください。")
    else:
        grouped_products = {}
        for product in st.session_state.recommended_products:
            category = product.get('商品カテゴリ', 'その他')
            if category not in grouped_products: grouped_products[category] = []
            grouped_products[category].append(product)
        
        current_selections = {}
        for category, products in grouped_products.items():
            with st.container(border=True):
                st.subheader(category)
                options = [f"{p['商品名']} (¥{int(p.get('価格',0)):,})" for p in products]
                product_map = {opt: prod for opt, prod in zip(options, products)}
                
                previous_selection = st.session_state.user_selections.get(category)
                previous_label = f"{previous_selection['商品名']} (¥{int(previous_selection.get('価格',0)):,})" if previous_selection else None
                current_index = options.index(previous_label) if previous_label in options else 0

                selected_label = st.radio(f"{category}選択", options, index=current_index, key=f"radio_{category}", label_visibility="collapsed")
                if selected_label:
                    selected_product = product_map[selected_label]
                    current_selections[category] = selected_product
                    st.info(f"**おすすめ理由:** {selected_product['おすすめ理由']}")
        
        st.session_state.user_selections = current_selections

# --- メイン処理 ---
def main():
    st.set_page_config(page_title="パーソナルスタイリングAI", layout="wide", initial_sidebar_state="auto")
    st.title("💄✂️ パーソナルスタイリングAI")
    initialize_session_state()
    
    # ★★★ ここにAPIキーを直接埋め込みます ★★★
    API_KEY = "YOUR_API_KEY" # <-- ここにあなたのAPIキーを貼り付けてください
    
    try: 
        genai.configure(api_key=API_KEY)
    except Exception as e: 
        st.error(f"APIキーの設定でエラーが発生しました: {e}")
        st.stop()
    
    if st.session_state.suggestion_generated:
        set_background_color(st.session_state.user_info.get('personal_color', '選択してください'))
    else:
        set_background_color('選択してください')
    
    left_col, right_col = st.columns([1, 1])
    with left_col: render_left_column()
    with right_col: render_right_column()
    
    render_sidebar()

if __name__ == "__main__":
    main()
