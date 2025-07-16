import streamlit as st
import google.generativeai as genai
import pandas as pd
import io

# --- 定数定義 ---
CSV_FILE_PATH = 'makeup_products.csv' # ここにあなたのCSVファイル名を設定

# CSVデータを外部ファイルから読み込み、整形する関数
@st.cache_data # Streamlitのキャッシュ機能を利用して、再実行時の読み込みを高速化
def load_and_process_makeup_data():
    """CSVデータを読み込み、整形してDataFrameを返す"""
    try:
        df = pd.read_csv(CSV_FILE_PATH, encoding='utf-8-sig')
        # '推奨パーソナルカラー'列のセミコロン区切りをリストに変換
        df['推奨パーソナルカラー'] = df['推奨パーソナルカラー'].apply(lambda x: [pc.strip() for pc in x.split(';')])
        # 価格列を数値型に変換（エラーがあればNaN）
        df['価格'] = pd.to_numeric(df['価格'], errors='coerce')
        return df
    except FileNotFoundError:
        st.error(f"エラー: CSVファイル '{CSV_FILE_PATH}' が見つかりません。Pythonスクリプトと同じディレクトリに配置してください。")
        st.stop() # アプリの実行を停止
    except Exception as e:
        st.error(f"CSVファイルの読み込み中にエラーが発生しました: {e}")
        st.stop()

# --- session_stateの初期化 ---
def initialize_session_state():
    """アプリで使うセッション変数を初期化する"""
    if 'style_suggestion' not in st.session_state:
        st.session_state.style_suggestion = None
    if 'diagnosis_step' not in st.session_state:
        st.session_state.diagnosis_step = 0
    if 'answers' not in st.session_state:
        st.session_state.answers = []
    if 'final_personal_color' not in st.session_state:
        st.session_state.final_personal_color = None
    if 'selected_personal_color' not in st.session_state:
        st.session_state.selected_personal_color = "選択してください"
    if 'waiting_for_diagnosis' not in st.session_state:
        st.session_state.waiting_for_diagnosis = False
    if 'style_suggested_flag' not in st.session_state:
        st.session_state.style_suggested_flag = False
    if 'cute_cool_value' not in st.session_state:
        st.session_state.cute_cool_value = 0 # 中央値
    if 'fresh_mature_value' not in st.session_state:
        st.session_state.fresh_mature_value = 0 # 中央値
    if 'show_more_base_makeup' not in st.session_state:
        st.session_state.show_more_base_makeup = False
    if 'show_more_eye_makeup' not in st.session_state:
        st.session_state.show_more_eye_makeup = False
    if 'show_more_lip_makeup' not in st.session_state:
        st.session_state.show_more_lip_makeup = False
    if 'show_more_cheek' not in st.session_state:
        st.session_state.show_more_cheek = False


# --- 背景色を設定する関数 ---
def set_background_color(personal_color_jp):
    """パーソナルカラーに基づいて背景色を設定する"""
    # 日本語のパーソナルカラーを内部的なキーに変換
    personal_color_map = {
        "イエベ春": "春",
        "イエベ秋": "秋",
        "ブルベ夏": "夏",
        "ブルベ冬": "冬",
        "選択してください": None # 初期選択は色なし
    }
    internal_color_key = personal_color_map.get(personal_color_jp)

    # 落ち着いた色のパレット
    color_map = {
        "春": "#FDF5E6",  # クリーム
        "夏": "#F0F8FF",  # アリスブルー
        "秋": "#FAFAD2",  # ライトゴールデンロッドイエロー
        "冬": "#E6E6FA",  # ラベンダー
    }
    
    # 背景色をリセットするスタイルをデフォルトに
    background_style = """
        <style>
        .stApp {
            background-color: #FFFFFF; /* デフォルトの白に戻す */
        }
        </style>
    """

    if internal_color_key and internal_color_key in color_map:
        background_style = f"""
            <style>
            .stApp {{
                background-color: {color_map.get(internal_color_key, '#FFFFFF')};
            }}
            </style>
        """
    
    st.markdown(background_style, unsafe_allow_html=True)


# --- サイドバーの描画 ---
def render_sidebar():
    """サイドバーとパーソナルカラー診断機能を描画する"""
    with st.sidebar:
        st.header("🎨 4シーズン・パーソナルカラー診断")
        st.write("より詳しい質問に答えて、あなたのシーズンを見つけましょう！")
        
        questions = [
            "Q1. あなたの瞳の色や印象は？", "Q2. アクセサリーを着けるなら、どちらが肌に馴染みますか？",
            "Q3. あなたの肌の質感は？", "Q4. あなたに似合うリップの色はどんな色ですか？"
        ]
        options = [
            ["A. キラキラと輝く明るい茶色", "B. マットで深みのあるこげ茶色", "C. ソフトで落ち着いた赤茶色や黒", "D. 白目と黒目のコントラストがはっきりした黒"],
            ["A. キラキラした明るいゴールド", "B. 黄みが強く、マットなゴールド", "C. 優しく光るプラチナやシルバー", "D. シャープに輝くプラチナやシルバー"],
            ["A. ツヤがあり、皮膚が薄め", "B. マットで、厚みを感じる", "C. サラサラで、少しマットな質感", "D. ハリがあり、しっかりしている"],
            ["A. 明るいコーラルピンクやオレンジ系", "B. 深みのあるテラコッタやブラウンレッド系", "C. 明るくソフトなローズピンク系", "D. 鮮やかなチェリーレッドやワインレッド系"]
        ]
        answer_to_season = {
            'Q1': {'A': '春', 'B': '秋', 'C': '夏', 'D': '冬'}, 'Q2': {'A': '春', 'B': '秋', 'C': '夏', 'D': '冬'},
            'Q3': {'A': '春', 'B': '秋', 'C': '夏', 'D': '冬'}, 'Q4': {'A': '春', 'B': '秋', 'C': '夏', 'D': '冬'},
        }

        if st.session_state.diagnosis_step == 0:
            if st.button("詳細診断を開始する"):
                st.session_state.diagnosis_step = 1
                st.session_state.answers = []
                st.session_state.final_personal_color = None # 診断開始時にリセット
                st.session_state.style_suggested_flag = False # 診断開始時にフラグをリセット
                st.rerun()
        elif st.session_state.diagnosis_step <= len(questions):
            q_index = st.session_state.diagnosis_step - 1
            st.write(f"**{questions[q_index]}**")
            col1, col2 = st.columns(2)
            with col1:
                if st.button(options[q_index][0], key=f"q{q_index}a", use_container_width=True):
                    st.session_state.answers.append('A')
                    st.session_state.diagnosis_step += 1
                    st.rerun()
                if st.button(options[q_index][2], key=f"q{q_index}c", use_container_width=True):
                    st.session_state.answers.append('C')
                    st.session_state.diagnosis_step += 1
                    st.rerun()
            with col2:
                if st.button(options[q_index][1], key=f"q{q_index}b", use_container_width=True):
                    st.session_state.answers.append('B')
                    st.session_state.diagnosis_step += 1
                    st.rerun()
                if st.button(options[q_index][3], key=f"q{q_index}d", use_container_width=True):
                    st.session_state.answers.append('D')
                    st.session_state.diagnosis_step += 1
                    st.rerun()
        else:
            scores = {'春': 0, '夏': 0, '秋': 0, '冬': 0}
            for i, ans in enumerate(st.session_state.answers):
                question_key = f'Q{i+1}'
                season = answer_to_season[question_key][ans]
                scores[season] += 1
            final_season = max(scores, key=scores.get)
            st.session_state.final_personal_color = final_season # 診断結果を保存
            
            season_descriptions = {
                "春": "あなたは**イエベ春**です！🌸 明るくクリアな色が似合います。",
                "秋": "あなたは**イエベ秋**です！🍁 深みのあるアースカラーが似合います。",
                "夏": "あなたは**ブルベ夏**です！💧 涼しげで穏やかな色が似合います。",
                "冬": "あなたは**ブルベ冬**です！❄️ はっきりとした鮮やかな色が似合います。"
            }
            st.subheader("診断結果")
            st.info(season_descriptions[final_season])

            # セレクトボックスの選択肢を診断結果に自動設定
            if st.session_state.final_personal_color:
                personal_color_display = {
                    "春": "イエベ春", "秋": "イエベ秋", "夏": "ブルベ夏", "冬": "ブルベ冬"
                }[st.session_state.final_personal_color]
                st.session_state.selected_personal_color = personal_color_display
                
            if st.button("もう一度診断する"):
                st.session_state.diagnosis_step = 0
                st.session_state.answers = []
                st.session_state.final_personal_color = None # リセット時に色もリセット
                st.session_state.selected_personal_color = "選択してください" # セレクトボックスもリセット
                st.session_state.waiting_for_diagnosis = False # 診断待ちフラグもリセット
                st.session_state.style_suggested_flag = False # スタイル提案フラグもリセット
                # カテゴリごとの「さらにおすすめを見る」表示フラグもリセット
                st.session_state.show_more_base_makeup = False
                st.session_state.show_more_eye_makeup = False
                st.session_state.show_more_lip_makeup = False
                st.session_state.show_more_cheek = False
                st.rerun()

# --- 各カテゴリの追加商品表示を切り替える関数 ---
def toggle_show_more(category_key):
    # クリックされたカテゴリ以外の表示フラグをすべてFalseにする
    all_categories = ['base_makeup', 'eye_makeup', 'lip_makeup', 'cheek']
    for cat in all_categories:
        if cat == category_key:
            # クリックされたカテゴリは現在の状態をトグルする（表示/非表示を切り替える）
            st.session_state[f'show_more_{cat}'] = not st.session_state[f'show_more_{cat}']
        else:
            # 他のカテゴリは非表示にする
            st.session_state[f'show_more_{cat}'] = False
    st.rerun()

# --- メインの処理 ---
def main():
    """メインのアプリケーション処理"""
    st.title("💄✂️ パーソナルスタイリングAI")
    st.markdown("あなたの特徴と「なりたいイメージ」から、おすすめのコスメと髪型を提案します。")
    
    # 背景色の設定ロジックをここに集約
    if st.session_state.style_suggested_flag and st.session_state.selected_personal_color != "選択してください":
        set_background_color(st.session_state.selected_personal_color)
    else:
        set_background_color("選択してください") # それ以外は常にデフォルトの白

    api_key = st.text_input("Gemini APIキーを入力してください:", type="password", help="Google AI StudioでAPIキーを取得してください")
    if not api_key:
        st.warning("Gemini APIキーを入力して、アプリの全機能をお楽しみください。")
        return
        
    genai.configure(api_key=api_key)

    # --- ユーザー入力 ---
    col1, col2 = st.columns(2)
    with col1:
        st.header("あなたの情報を入力")
        personal_color_options = ["選択してください", "イエベ春", "イエベ秋", "ブルベ夏", "ブルベ冬"]
        
        # セレクトボックスの初期値を設定
        initial_index = personal_color_options.index(st.session_state.selected_personal_color)
        
        selected_pc = st.selectbox(
            "パーソナルカラー", 
            personal_color_options, 
            index=initial_index, 
            key="main_personal_color_select" # キーを追加
        )
        
        # セレクトボックスの値が変更されたらセッション状態を更新
        if selected_pc != st.session_state.selected_personal_color:
            st.session_state.selected_personal_color = selected_pc

        face_shape = st.selectbox("顔の形", ("丸顔", "面長", "卵型", "ベース型", "逆三角形"))
        
        # なりたいイメージをスライダーで設定
        st.markdown("### なりたいイメージを調整")
        
        # かわいい ↔ かっこいい スライダー
        cute_cool = st.slider(
            "かわいい ↔ かっこいい",
            min_value=-5, max_value=5, value=st.session_state.cute_cool_value, step=1,
            key="cute_cool_slider"
        )
        # スライダーの値をわかりやすいテキストで表示
        cute_cool_text_map = {
            -5: "かわいいさMAX", -4: "とてもかわいい", -3: "ややかわいい", -2: "ちょっとかわいい", -1: "普通",
            0: "いいとこどり！",
            1: "普通", 2: "ちょっとかっこいい", 3: "ややかっこいい", 4: "とてもかっこいい", 5: "かっこよさMAX"
        }
        st.write(f"現在の設定: **{cute_cool_text_map.get(cute_cool, 'いいとこどり！')}**")
        
        # スライダーの値が変更されたらセッション状態を更新
        if cute_cool != st.session_state.cute_cool_value:
            st.session_state.cute_cool_value = cute_cool
            st.rerun() # スライダーの値を変更した時に表示テキストも更新するためリラン

        # フレッシュ ↔ 大人っぽい スライダー
        fresh_mature = st.slider(
            "フレッシュ ↔ 大人っぽい",
            min_value=-5, max_value=5, value=st.session_state.fresh_mature_value, step=1,
            key="fresh_mature_slider"
        )
        # スライダーの値をわかりやすいテキストで表示
        fresh_mature_text_map = {
            -5: "フレッシュさMAX", -4: "とてもフレッシュ", -3: "ややフレッシュ", -2: "ちょっとフレッシュ", -1: "普通",
            0: "いいとこどり！",
            1: "普通", 2: "ちょっと大人っぽい", 3: "やや大人っぽい", 4: "とても大人っぽい", 5: "大人っぽさMAX"
        }
        st.write(f"現在の設定: **{fresh_mature_text_map.get(fresh_mature, 'いいとこどり！')}**")

        # スライダーの値が変更されたらセッション状態を更新
        if fresh_mature != st.session_state.fresh_mature_value:
            st.session_state.fresh_mature_value = fresh_mature
            st.rerun() # スライダーの値を変更した時に表示テキストも更新するためリラン

        # スライダーの値から「なりたいイメージ」を組み立てる
        desired_image_parts = []
        if cute_cool != 0:
            desired_image_parts.append(cute_cool_text_map[cute_cool])
        if fresh_mature != 0:
            desired_image_parts.append(fresh_mature_text_map[fresh_mature])
        
        if not desired_image_parts:
            desired_image_str = "いいとこどり！"
        else:
            desired_image_str = "、".join(desired_image_parts)

    with col2:
        st.empty()

    # --- テキスト提案 ---
    if st.button("おすすめのスタイルを提案してもらう"):
        # セレクトボックスで「選択してください」が選ばれている場合は警告
        if st.session_state.selected_personal_color == "選択してください":
            st.warning("パーソナルカラーを選択してください。")
            return
            
        st.session_state.waiting_for_diagnosis = True # 診断開始フラグを立てる
        st.session_state.style_suggested_flag = False # 新しい提案が始まるのでリセット
        # カテゴリごとの「さらにおすすめを見る」表示フラグもリセット
        st.session_state.show_more_base_makeup = False
        st.session_state.show_more_eye_makeup = False
        st.session_state.show_more_lip_makeup = False
        st.session_state.show_more_cheek = False

        try:
            with st.spinner('AIがあなたにぴったりのスタイルを考えています...'):
                # CSVデータをDataFrameに読み込み、整形
                df = load_and_process_makeup_data()
                # DataFrameを文字列として渡す前に、リスト形式のパーソナルカラーをセミコロン区切りに戻す
                df_for_prompt = df.copy()
                df_for_prompt['推奨パーソナルカラー'] = df_for_prompt['推奨パーソナルカラー'].apply(lambda x: ';'.join(x))
                product_list_str = df_for_prompt.to_string(index=False) # index=FalseでDataFrameのインデックスを非表示に

                text_prompt = f"""あなたはプロのパーソナルスタイリストです。以下のユーザー情報を総合的に分析し、最適な「メイク用品」と「髪型」を提案してください。提供されたCSVの商品リストから適切な商品を選定し、提案の理由は具体的に、以下のフォーマットで記述してください。各カテゴリで**最大3つ**の商品を提案してください。

# ユーザー情報: パーソナルカラー: {st.session_state.selected_personal_color}, 顔の形: {face_shape}, なりたいイメージ: {desired_image_str}

# 商品リストの形式: 商品名,ブランド名,価格,特徴,推奨パーソナルカラー,商品カテゴリ
# 注意: 推奨パーソナルカラーはセミコロン(;)で区切られています。商品カテゴリは「ベースメイク」「リップ」「チーク」「アイシャドウ」のいずれかです。
{product_list_str}

## あなたへのトータルスタイリング提案 ✨

### **ヘアスタイル**
* **提案**: [具体的な髪型を提案]
* **理由**: [理由]

### **ベースメイク**
* **商品名**: [CSVから選定したベースメイクの商品名], **ブランド**: [ブランド名], **おすすめ理由**: [理由]
* **商品名**: [CSVから選定したベースメイクの商品名], **ブランド**: [ブランド名], **おすすめ理由**: [理由]
* **商品名**: [CSVから選定したベースメイクの商品名], **ブランド**: [ブランド名], **おすすめ理由**: [理由]

### **アイメイク**
* **商品名**: [CSVから選定したアイメイクの商品名], **ブランド**: [ブランド名], **おすすめ理由**: [理由]
* **商品名**: [CSVから選定したアイメイクの商品名], **ブランド**: [ブランド名], **おすすめ理由**: [理由]
* **商品名**: [CSVから選定したアイメイクの商品名], **ブランド**: [ブランド名], **おすすめ理由**: [理由]

### **リップメイク**
* **商品名**: [CSVから選定したリップメイクの商品名], **ブランド**: [ブランド名], **おすすめ理由**: [理由]
* **商品名**: [CSVから選定したリップメイクの商品名], **ブランド**: [ブランド名], **おすすめ理由**: [理由]
* **商品名**: [CSVから選定したリップメイクの商品名], **ブランド**: [ブランド名], **おすすめ理由**: [理由]

### **チーク**
* **商品名**: [CSVから選定したチークの商品名], **ブランド**: [ブランド名], **おすすめ理由**: [理由]
* **商品名**: [CSVから選定したチークの商品名], **ブランド**: [ブランド名], **おすすめ理由**: [理由]
* **商品名**: [CSVから選定したチークの商品名], **ブランド**: [ブランド名], **おすすめ理由**: [理由]
"""
                
                model = genai.GenerativeModel('gemini-1.5-flash')
                response = model.generate_content(text_prompt) 
                
                st.session_state.style_suggestion = response.text
                st.session_state.waiting_for_diagnosis = False # 診断完了フラグを下げる
                st.session_state.style_suggested_flag = True # スタイル提案完了フラグを立てる
                st.rerun() # 再実行して背景色を適用

        except FileNotFoundError:
            st.session_state.waiting_for_diagnosis = False
            st.session_state.style_suggested_flag = False
            st.error(f"エラー: CSVファイル '{CSV_FILE_PATH}' が見つかりません。Pythonスクリプトと同じディレクトリに配置してください。")
        except Exception as e:
            st.session_state.waiting_for_diagnosis = False
            st.session_state.style_suggested_flag = False
            st.error(f"エラーが発生しました: {e}")
            st.exception(e) # 詳細なエラーメッセージを表示

    if st.session_state.style_suggestion:
        st.markdown("---")
        st.markdown("### AIからのスタイリング提案")
        st.markdown(st.session_state.style_suggestion)

        # 各カテゴリの「さらにおすすめを見る」ボタン
        st.markdown("---")
        st.subheader("さらに他の商品も見てみましょう！")

        col_base, col_eye, col_lip, col_cheek = st.columns(4)

        with col_base:
            if st.button("ベースメイクのおすすめを見る", key="more_base_makeup"):
                toggle_show_more('base_makeup')
        with col_eye:
            if st.button("アイメイクのおすすめを見る", key="more_eye_makeup"):
                toggle_show_more('eye_makeup')
        with col_lip:
            if st.button("リップメイクのおすすめを見る", key="more_lip_makeup"):
                toggle_show_more('lip_makeup')
        with col_cheek:
            if st.button("チークのおすすめを見る", key="more_cheek"):
                toggle_show_more('cheek')
        
        # 「さらにおすすめを見る」がクリックされた場合に表示するロジック
        df = load_and_process_makeup_data() # 最新のデータをロード

        personal_color_filter = st.session_state.selected_personal_color
        
        # フィルタリング関数
        def filter_products(df, category, pc_filter):
            # '全パーソナルカラー' または選択されたパーソナルカラーを含む商品をフィルタリング
            filtered_df = df[(df['商品カテゴリ'] == category) & 
                             (df['推奨パーソナルカラー'].apply(lambda x: pc_filter in x or '全パーソナルカラー' in x))]
            return filtered_df.sort_values(by='価格').drop_duplicates(subset=['商品名', 'ブランド名']) # 価格でソートし、重複を削除

        if st.session_state.show_more_base_makeup:
            st.markdown("#### さらに多くのベースメイク")
            filtered_base_makeup = filter_products(df, "ベースメイク", personal_color_filter)
            if not filtered_base_makeup.empty:
                for idx, row in filtered_base_makeup.head(5).iterrows(): # 上位5件を表示
                    st.write(f"**商品名**: {row['商品名']}, **ブランド**: {row['ブランド名']}, **価格**: ¥{row['価格']:,}, **特徴**: {row['特徴']}")
            else:
                st.write("この条件に合うベースメイクは見つかりませんでした。")
            # 「閉じる」ボタンは表示しない

        if st.session_state.show_more_eye_makeup:
            st.markdown("#### さらに多くのアイメイク")
            # CSVのカテゴリ名が「アイシャドウ」なので、それに合わせる
            filtered_eye_makeup = filter_products(df, "アイシャドウ", personal_color_filter) 
            if not filtered_eye_makeup.empty:
                for idx, row in filtered_eye_makeup.head(5).iterrows():
                    st.write(f"**商品名**: {row['商品名']}, **ブランド**: {row['ブランド名']}, **価格**: ¥{row['価格']:,}, **特徴**: {row['特徴']}")
            else:
                st.write("この条件に合うアイメイクは見つかりませんでした。")
            # 「閉じる」ボタンは表示しない

        if st.session_state.show_more_lip_makeup:
            st.markdown("#### さらに多くのリップメイク")
            filtered_lip_makeup = filter_products(df, "リップ", personal_color_filter)
            if not filtered_lip_makeup.empty:
                for idx, row in filtered_lip_makeup.head(5).iterrows():
                    st.write(f"**商品名**: {row['商品名']}, **ブランド**: {row['ブランド名']}, **価格**: ¥{row['価格']:,}, **特徴**: {row['特徴']}")
            else:
                st.write("この条件に合うリップメイクは見つかりませんでした。")
            # 「閉じる」ボタンは表示しない

        if st.session_state.show_more_cheek:
            st.markdown("#### さらに多くのチーク")
            filtered_cheek = filter_products(df, "チーク", personal_color_filter)
            if not filtered_cheek.empty:
                for idx, row in filtered_cheek.head(5).iterrows():
                    st.write(f"**商品名**: {row['商品名']}, **ブランド**: {row['ブランド名']}, **価格**: ¥{row['価格']:,}, **特徴**: {row['特徴']}")
            else:
                st.write("この条件に合うチークは見つかりませんでした。")
            # 「閉じる」ボタンは表示しない

        st.markdown("---")

# --- アプリの実行 ---
if __name__ == "__main__":
    initialize_session_state()
    render_sidebar()
    main()