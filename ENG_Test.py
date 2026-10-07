import csv
from datetime import datetime
import io
import json
import os
import random
from gtts import gTTS
import streamlit as st
import streamlit.components.v1 as components

SESSION_COUNT = 5
CSV_FILE_PATH = "words.csv"


def parse_example(example_raw: str):
  if not example_raw:
    return "", ""
  if "||" in example_raw:
    parts = example_raw.split("||")
    return parts[0].strip(), parts[1].strip()
  return example_raw.strip(), ""


@st.cache_data
def load_words_from_csv(file_path: str):
  categories = {}
  if not os.path.exists(file_path):
    return categories

  with open(file_path, mode="r", encoding="utf-8-sig") as f:
    reader = csv.DictReader(f)
    for row in reader:
      clean_row = {
          (k.strip() if k else ""): (v.strip() if v else "")
          for k, v in row.items()
      }
      cat = clean_row.get("category") or clean_row.get("分類") or "未分類"
      word = clean_row.get("word") or clean_row.get("單字") or ""
      definition = (
          clean_row.get("def")
          or clean_row.get("definition")
          or clean_row.get("meaning")
          or clean_row.get("釋義")
          or ""
      )
      example = clean_row.get("example") or clean_row.get("例句") or ""

      if not word or not definition:
        continue

      if cat not in categories:
        categories[cat] = []
      categories[cat].append(
          {"word": word, "def": definition, "example": example}
      )
  return categories


@st.cache_data
def get_audio_bytes(text: str) -> bytes:
  clean_text = text.strip()
  tts = gTTS(text=clean_text, lang="en", tld="com", slow=False)
  fp = io.BytesIO()
  tts.write_to_fp(fp)
  fp.seek(0)
  return fp.read()


# ==================== 原生 JavaScript 瀏覽器本機儲存 (LocalStorage) ====================
def save_browser_data(key: str, data):
  """使用原生 JavaScript 寫入使用者的手機/電腦 LocalStorage"""
  json_str = json.dumps(data, ensure_ascii=False)
  safe_json = json_str.replace("\\", "\\\\").replace("'", "\\'")
  html_script = f"""
    <script>
        try {{
            window.parent.localStorage.setItem('{key}', '{safe_json}');
        }} catch(e) {{
            console.error('LocalStorage Write Error:', e);
        }}
    </script>
    """
  components.html(html_script, height=0, width=0)


def init_session(category_name: str, categories_db: dict, custom_pool=None):
  category_pool = (
      custom_pool
      if custom_pool is not None
      else categories_db.get(category_name, [])
  )
  if not category_pool:
    return

  count = min(SESSION_COUNT, len(category_pool))
  selected_words = random.sample(category_pool, count)

  st.session_state.current_category = category_name
  st.session_state.selected_words = selected_words
  st.session_state.mode = "STUDY"
  st.session_state.study_index = 0

  st.session_state.quiz_step = 0
  st.session_state.score = 0
  st.session_state.wrong_answers = []
  st.session_state.current_quiz_records = []
  st.session_state.cleared_words = []

  # 干擾項選項生成
  all_defs = [w["def"] for w in category_pool if w.get("def")]
  if len(all_defs) < 4:
    global_defs = [
        item["def"]
        for items in categories_db.values()
        for item in items
        if item.get("def")
    ]
    all_defs.extend(
        random.sample(global_defs, min(10, len(global_defs)))
        if global_defs
        else []
    )

  quiz_questions = []
  for item in selected_words:
    other_defs = [d for d in all_defs if d != item["def"]]
    distractors = (
        random.sample(other_defs, min(3, len(other_defs)))
        if other_defs
        else ["選項 A", "選項 B", "選項 C"]
    )
    options = distractors + [item["def"]]
    random.shuffle(options)

    quiz_questions.append({
        "word": item["word"],
        "correct_def": item["def"],
        "example": item.get("example", ""),
        "options": options,
    })
  random.shuffle(quiz_questions)
  st.session_state.quiz_questions = quiz_questions


def start_weakness_quiz(weak_pool, categories_db):
  init_session("🎯 弱點加強專項", categories_db, custom_pool=weak_pool)
  st.session_state.selected_nav = "📝 單字學習與測驗"


# ==================== 頁面配置 ====================
st.set_page_config(
    page_title="單字學習與測驗系統", page_icon="🎓", layout="centered"
)
CATEGORIES_DB = load_words_from_csv(CSV_FILE_PATH)

if not CATEGORIES_DB:
  st.error(f"⚠️ 找不到 `{CSV_FILE_PATH}` 檔案或檔案內沒有單字資料！")
  st.stop()

# 初始化 session 狀態變數
if "quiz_history" not in st.session_state:
  st.session_state.quiz_history = []

if "wrong_words_db" not in st.session_state:
  st.session_state.wrong_words_db = {}

if "selected_nav" not in st.session_state:
  st.session_state.selected_nav = "📝 單字學習與測驗"

if "total_cleared_count" not in st.session_state:
  st.session_state.total_cleared_count = 0

if "cleared_words" not in st.session_state:
  st.session_state.cleared_words = []

if "current_category" not in st.session_state or (
    st.session_state.current_category not in CATEGORIES_DB
    and st.session_state.current_category != "🎯 弱點加強專項"
):
  default_cat = list(CATEGORIES_DB.keys())[0]
  init_session(default_cat, CATEGORIES_DB)


# ==================== 輔助：計算 4 大類各 20 個成就徽章 (帶特性圖示的分頁標題) ====================
def calculate_categorized_badges(history, cleared_count):
  total_rounds = len(history)
  total_correct = sum(h["score"] for h in history)

  # 計算歷史最大連續滿分輪數
  max_streak = 0
  cur_streak = 0
  for h in history:
    if h["score"] == h["total"] and h["total"] > 0:
      cur_streak += 1
      max_streak = max(max_streak, cur_streak)
    else:
      cur_streak = 0

  categories = {
      # 1. 輪數挑戰 (20 個，最高 1000 輪) - 特性圖案：🏃 奔馳長征
      "🏃 輪數長征": [
          {"name": "初試啼聲", "target": 1, "icon": "🌱", "curr": total_rounds, "unit": "輪"},
          {"name": "步入正軌", "target": 3, "icon": "🌿", "curr": total_rounds, "unit": "輪"},
          {"name": "漸入佳境", "target": 5, "icon": "🍃", "curr": total_rounds, "unit": "輪"},
          {"name": "十全學徒", "target": 10, "icon": "🥉", "curr": total_rounds, "unit": "輪"},
          {"name": "勤奮不懈", "target": 20, "icon": "🥈", "curr": total_rounds, "unit": "輪"},
          {"name": "毅力堅持", "target": 30, "icon": "🥇", "curr": total_rounds, "unit": "輪"},
          {"name": "半百里程", "target": 50, "icon": "🏆", "curr": total_rounds, "unit": "輪"},
          {"name": "百鍊成鋼", "target": 75, "icon": "🎖️", "curr": total_rounds, "unit": "輪"},
          {"name": "百輪傳奇", "target": 100, "icon": "👑", "curr": total_rounds, "unit": "輪"},
          {"name": "勢如破竹", "target": 150, "icon": "🚀", "curr": total_rounds, "unit": "輪"},
          {"name": "恆星長征", "target": 200, "icon": "🌌", "curr": total_rounds, "unit": "輪"},
          {"name": "穿越星際", "target": 300, "icon": "🛸", "curr": total_rounds, "unit": "輪"},
          {"name": "鐵人意志", "target": 400, "icon": "⚔️", "curr": total_rounds, "unit": "輪"},
          {"name": "半千殿堂", "target": 500, "icon": "💎", "curr": total_rounds, "unit": "輪"},
          {"name": "永不止步", "target": 600, "icon": "🌪️", "curr": total_rounds, "unit": "輪"},
          {"name": "堅如磐石", "target": 700, "icon": "🏰", "curr": total_rounds, "unit": "輪"},
          {"name": "光芒萬丈", "target": 800, "icon": "🌠", "curr": total_rounds, "unit": "輪"},
          {"name": "九霄雲上", "target": 900, "icon": "🐉", "curr": total_rounds, "unit": "輪"},
          {"name": "登峰極致", "target": 950, "icon": "🪐", "curr": total_rounds, "unit": "輪"},
          {"name": "千輪千秋", "target": 1000, "icon": "☀️", "curr": total_rounds, "unit": "輪"},
      ],
      # 2. 滿分連勝 (20 個，最高 200 輪) - 特性圖案：🔥 連續熾熱連勝
      "🔥 滿分連勝": [
          {"name": "完美首勝", "target": 1, "icon": "💯", "curr": max_streak, "unit": "輪"},
          {"name": "雙喜臨門", "target": 2, "icon": "✌️", "curr": max_streak, "unit": "輪"},
          {"name": "連中三元", "target": 3, "icon": "🔥", "curr": max_streak, "unit": "輪"},
          {"name": "四季常勝", "target": 4, "icon": "⚡", "curr": max_streak, "unit": "輪"},
          {"name": "五星連珠", "target": 5, "icon": "🌟", "curr": max_streak, "unit": "輪"},
          {"name": "七星貫日", "target": 7, "icon": "🎯", "curr": max_streak, "unit": "輪"},
          {"name": "十全十美", "target": 10, "icon": "👑", "curr": max_streak, "unit": "輪"},
          {"name": "十五破浪", "target": 15, "icon": "🌊", "curr": max_streak, "unit": "輪"},
          {"name": "勢不可擋", "target": 20, "icon": "🚀", "curr": max_streak, "unit": "輪"},
          {"name": "連戰皆捷", "target": 30, "icon": "⚔️", "curr": max_streak, "unit": "輪"},
          {"name": "百發百中", "target": 40, "icon": "🏹", "curr": max_streak, "unit": "輪"},
          {"name": "半百神射", "target": 50, "icon": "🏆", "curr": max_streak, "unit": "輪"},
          {"name": "六六大順", "target": 60, "icon": "🌠", "curr": max_streak, "unit": "輪"},
          {"name": "八方無敵", "target": 80, "icon": "🔱", "curr": max_streak, "unit": "輪"},
          {"name": "百步穿楊", "target": 100, "icon": "🥇", "curr": max_streak, "unit": "輪"},
          {"name": "神乎其技", "target": 120, "icon": "🔮", "curr": max_streak, "unit": "輪"},
          {"name": "天人合一", "target": 140, "icon": "🥋", "curr": max_streak, "unit": "輪"},
          {"name": "超凡入聖", "target": 160, "icon": "🐉", "curr": max_streak, "unit": "輪"},
          {"name": "萬佛朝宗", "target": 180, "icon": "🪷", "curr": max_streak, "unit": "輪"},
          {"name": "雙百封神", "target": 200, "icon": "👑", "curr": max_streak, "unit": "輪"},
      ],
      # 3. 弱點消除 (20 個，最高 500 個) - 特性圖案：🛡️ 防禦與弱點粉碎
      "🛡️ 弱點粉碎": [
          {"name": "破繭而出", "target": 1, "icon": "🧹", "curr": cleared_count, "unit": "個"},
          {"name": "查漏補缺", "target": 3, "icon": "🧼", "curr": cleared_count, "unit": "個"},
          {"name": "初步克難", "target": 5, "icon": "🔧", "curr": cleared_count, "unit": "個"},
          {"name": "障礙粉碎", "target": 10, "icon": "🔨", "curr": cleared_count, "unit": "個"},
          {"name": "堅固防線", "target": 15, "icon": "🛡️", "curr": cleared_count, "unit": "個"},
          {"name": "弱點獵人", "target": 20, "icon": "⚔️", "curr": cleared_count, "unit": "個"},
          {"name": "掃蕩狂風", "target": 30, "icon": "🌪️", "curr": cleared_count, "unit": "個"},
          {"name": "牢不可破", "target": 40, "icon": "🏰", "curr": cleared_count, "unit": "個"},
          {"name": "無懈可擊", "target": 50, "icon": "💎", "curr": cleared_count, "unit": "個"},
          {"name": "錯題剋星", "target": 75, "icon": "⚡", "curr": cleared_count, "unit": "個"},
          {"name": "百毒不侵", "target": 100, "icon": "🛸", "curr": cleared_count, "unit": "個"},
          {"name": "銳不可當", "target": 150, "icon": "🗡️", "curr": cleared_count, "unit": "個"},
          {"name": "詞林肅清", "target": 200, "icon": "🌊", "curr": cleared_count, "unit": "個"},
          {"name": "半千之半", "target": 250, "icon": "🥉", "curr": cleared_count, "unit": "個"},
          {"name": "弱點收割者", "target": 300, "icon": "🥈", "curr": cleared_count, "unit": "個"},
          {"name": "鋼鐵防線", "target": 350, "icon": "🥇", "curr": cleared_count, "unit": "個"},
          {"name": "千錘百鍊", "target": 400, "icon": "🌋", "curr": cleared_count, "unit": "個"},
          {"name": "無瑕之鏡", "target": 450, "icon": "🪞", "curr": cleared_count, "unit": "個"},
          {"name": "終極淨化", "target": 480, "icon": "✨", "curr": cleared_count, "unit": "個"},
          {"name": "五百完美守護", "target": 500, "icon": "👑", "curr": cleared_count, "unit": "個"},
      ],
      # 4. 答對總量 (20 個，最高 5000 題) - 特性圖案：👑 詞彙量宗師殿堂
      "👑 詞彙巔峰": [
          {"name": "單字起步", "target": 10, "icon": "📖", "curr": total_correct, "unit": "題"},
          {"name": "實力初顯", "target": 25, "icon": "📝", "curr": total_correct, "unit": "題"},
          {"name": "單字健將", "target": 50, "icon": "🎯", "curr": total_correct, "unit": "題"},
          {"name": "博聞強記", "target": 100, "icon": "📜", "curr": total_correct, "unit": "題"},
          {"name": "單字學者", "target": 200, "icon": "💡", "curr": total_correct, "unit": "題"},
          {"name": "詞海漫遊", "target": 300, "icon": "🏹", "curr": total_correct, "unit": "題"},
          {"name": "單字大師", "target": 500, "icon": "👑", "curr": total_correct, "unit": "題"},
          {"name": "學海無涯", "target": 750, "icon": "📚", "curr": total_correct, "unit": "題"},
          {"name": "千字通關", "target": 1000, "icon": "💎", "curr": total_correct, "unit": "題"},
          {"name": "博學篤行", "target": 1500, "icon": "🎖️", "curr": total_correct, "unit": "題"},
          {"name": "雙千傳奇", "target": 2000, "icon": "🪐", "curr": total_correct, "unit": "題"},
          {"name": "詞彙半壁", "target": 2500, "icon": "🏔️", "curr": total_correct, "unit": "題"},
          {"name": "萬卷之始", "target": 3000, "icon": "🌌", "curr": total_correct, "unit": "題"},
          {"name": "智慧長河", "target": 3500, "icon": "🌊", "curr": total_correct, "unit": "題"},
          {"name": "字字珠璣", "target": 4000, "icon": "🔮", "curr": total_correct, "unit": "題"},
          {"name": "學貫中西", "target": 4200, "icon": "🏛️", "curr": total_correct, "unit": "題"},
          {"name": "登峰造極", "target": 4500, "icon": "🚀", "curr": total_correct, "unit": "題"},
          {"name": "通天徹地", "target": 4800, "icon": "⚡", "curr": total_correct, "unit": "題"},
          {"name": "超神之巔", "target": 4900, "icon": "🌟", "curr": total_correct, "unit": "題"},
          {"name": "五千神諭宗師", "target": 5000, "icon": "☀️", "curr": total_correct, "unit": "題"},
      ],
  }

  formatted_cat = {}
  total_badges_count = 0
  total_unlocked_count = 0

  for cat_name, b_list in categories.items():
    formatted_cat[cat_name] = []
    for item in b_list:
      total_badges_count += 1
      is_unlocked = item["curr"] >= item["target"]
      if is_unlocked:
        total_unlocked_count += 1
      formatted_cat[cat_name].append({
          "name": item["name"],
          "desc": f"累計達成 {item['target']} {item['unit']}",
          "icon": item["icon"],
          "progress": f"{min(item['curr'], item['target'])} / {item['target']}{item['unit']}",
          "unlocked": is_unlocked,
      })

  return formatted_cat, total_unlocked_count, total_badges_count


# ==================== 側邊欄控制 ====================
with st.sidebar:
  st.header("⚙️ 題庫與功能選單")

  app_view = st.radio(
      "功能切換：",
      [
          "📝 單字學習與測驗",
          "🎯 個人弱點加強庫",
          "🏆 學習成就與儀表板",
          "📜 歷史考題回顧",
      ],
      key="selected_nav",
  )
  st.write("---")

  wrong_db = st.session_state.wrong_words_db
  st.metric(label="🎯 本機弱點單字量", value=f"{len(wrong_db)} 個")
  st.caption(f"💾 本次會話紀錄：**{len(st.session_state.quiz_history)}** 輪")
  st.caption("🔒 模式：**獨立裝置本地儲存（不與他人共用）**")

  category_list = list(CATEGORIES_DB.keys())
  cur_cat = (
      st.session_state.current_category
      if st.session_state.current_category in category_list
      else category_list[0]
  )
  current_cat_idx = category_list.index(cur_cat)

  selected_category = st.selectbox(
      "選擇練習類別：", category_list, index=current_cat_idx
  )

  current_total = len(CATEGORIES_DB[selected_category])
  st.info(f"📊 本類別總題庫量：**{current_total}** 個單字")
  st.caption(f"🎯 每次學習：**{SESSION_COUNT}** 個單字")

  if (
      st.session_state.current_category != "🎯 弱點加強專項"
      and selected_category != st.session_state.current_category
      and app_view == "📝 單字學習與測驗"
  ):
    init_session(selected_category, CATEGORIES_DB)
    st.rerun()

  if st.button(f"重新抽選本類別 {SESSION_COUNT} 題 🎲", use_container_width=True):
    init_session(selected_category, CATEGORIES_DB)
    st.session_state.selected_nav = "📝 單字學習與測驗"
    st.rerun()

  st.write("---")
  if wrong_db and st.button("🧹 清空本機弱點庫", use_container_width=True):
    st.session_state.wrong_words_db = {}
    save_browser_data("wrong_words", {})
    st.success("已清空本裝置弱點庫！")
    st.rerun()

  if st.session_state.quiz_history and st.button(
      "🗑️ 清空歷史紀錄", use_container_width=True
  ):
    st.session_state.quiz_history = []
    st.session_state.total_cleared_count = 0
    save_browser_data("quiz_history", [])
    st.success("已清空紀錄！")
    st.rerun()


# ==================== 視圖 1：個人弱點加強庫 ====================
if app_view == "🎯 個人弱點加強庫":
  st.title("🎯 個人弱點加強庫")
  wrong_db = st.session_state.wrong_words_db

  if not wrong_db:
    st.success("🎉 太棒了！這台裝置上目前沒有累積任何錯題弱點！")
  else:
    sorted_wrongs = sorted(
        wrong_db.values(), key=lambda x: x["count"], reverse=True
    )
    st.write(
        f"本機共儲存 **{len(sorted_wrongs)}** 個曾答錯的單字（依答錯頻率排列）："
    )

    if len(sorted_wrongs) >= 5:
      weak_pool = [
          {
              "word": item["word"],
              "def": item["def"],
              "example": item.get("example", ""),
          }
          for item in sorted_wrongs
      ]
      st.button(
          "🚀 開始弱點專項加強測驗（隨機抽 5 題）",
          type="primary",
          use_container_width=True,
          on_click=start_weakness_quiz,
          args=(weak_pool, CATEGORIES_DB),
      )
    else:
      st.caption(
          f"💡 弱點單字需累積滿 5 個即可啟動專項測驗（目前本機累積"
          f" {len(sorted_wrongs)} 個）。"
      )

    st.divider()

    for idx, item in enumerate(sorted_wrongs):
      col1, col2 = st.columns([4, 1])
      with col1:
        st.markdown(
            f"### {idx + 1}. **{item['word']}**  `累計答錯 {item['count']} 次`"
        )
        st.write(
            f"**釋義：** {item['def']}  ｜  **領域：**"
            f" {item.get('category', '弱點庫')}"
        )
        st.caption("單字發音：")
        st.audio(get_audio_bytes(item["word"]), format="audio/mp3")
        if item.get("example"):
          en_ex, ch_ex = parse_example(item["example"])
          if en_ex:
            st.caption(f"📖 例句：{en_ex}")
      with col2:
        if st.button("已熟記移除 ✕", key=f"del_wrong_{item['word']}"):
          del st.session_state.wrong_words_db[item["word"]]
          st.session_state.total_cleared_count += 1
          save_browser_data("wrong_words", st.session_state.wrong_words_db)
          st.rerun()
      st.divider()


# ==================== 視圖 2：學習成就與儀表板 (帶特性圖示分頁標題) ====================
elif app_view == "🏆 學習成就與儀表板":
  st.title("🏆 學習成就與儀表板")
  st.caption("視覺化追蹤每一次進步，收集解鎖 80 枚成就勳章！")

  history = st.session_state.quiz_history
  categorized_badges, unlocked_cnt, total_cnt = calculate_categorized_badges(
      history, st.session_state.total_cleared_count
  )

  # 區塊 A：整體成就解鎖進度
  st.subheader(f"🎖️ 成就勳章總覽（已解鎖 {unlocked_cnt} / {total_cnt}）")
  st.progress(unlocked_cnt / total_cnt)

  # 渲染帶有個性圖示的四大分類分頁
  tab_names = list(categorized_badges.keys())
  tabs = st.tabs(tab_names)

  for tab_idx, cat_name in enumerate(tab_names):
    with tabs[tab_idx]:
      badges = categorized_badges[cat_name]
      cat_unlocked = sum(1 for b in badges if b["unlocked"])
      st.caption(f"📊 {cat_name} 進度：已解鎖 **{cat_unlocked} / {len(badges)}** 枚")

      # 5 欄排版，20 個徽章剛好整齊排成 4 列
      b_cols = st.columns(5)
      for b_idx, b in enumerate(badges):
        col = b_cols[b_idx % 5]
        with col:
          if b["unlocked"]:
            st.success(
                f"### {b['icon']}\n**{b['name']}**\n\n`{b['desc']}`\n\n✅ *已解鎖*\n\n({b['progress']})"
            )
          else:
            st.info(
                f"### 🔒\n**{b['name']}**\n\n`{b['desc']}`\n\n⏳ *未解鎖*\n\n({b['progress']})"
            )

  st.divider()

  if not history:
    st.info("💡 尚未完成任何測驗，進行幾輪測驗後這裡將會展示您的進步走勢圖！")
  else:
    # 區塊 B：統計 KPI 卡片
    total_rounds = len(history)
    total_questions = sum(h["total"] for h in history)
    total_score = sum(h["score"] for h in history)
    avg_rate = (total_score / total_questions) * 100 if total_questions else 0

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("總測驗輪數", f"{total_rounds} 輪")
    m2.metric("總答題數", f"{total_questions} 題")
    m3.metric("累計答對", f"{total_score} 題")
    m4.metric("平均答對率", f"{avg_rate:.1f}%")

    st.write("")

    # 區塊 C：趨勢折線圖
    st.subheader("📈 最近測驗成績走勢 (換算滿分 100)")
    recent_history = history[-15:] if len(history) > 15 else history
    chart_scores = [
        round((h["score"] / h["total"]) * 100) for h in recent_history
    ]
    st.line_chart(chart_scores)

    # 區塊 D：分類掌握度長條圖
    st.subheader("📊 各領域答對率統計 (%)")
    cat_stats = {}
    for h in history:
      c = h["category"]
      if c not in cat_stats:
        cat_stats[c] = {"score": 0, "total": 0}
      cat_stats[c]["score"] += h["score"]
      cat_stats[c]["total"] += h["total"]

    cat_rates = {
        cat: round((data["score"] / data["total"]) * 100, 1)
        for cat, data in cat_stats.items()
        if data["total"] > 0
    }
    st.bar_chart(cat_rates)


# ==================== 視圖 3：歷史考題回顧 ====================
elif app_view == "📜 歷史考題回顧":
  st.title("📜 歷史考題詳細回顧")
  st.caption("完整記錄歷次測驗分數、各題作答詳情與原聲發音。")

  history = st.session_state.quiz_history

  if not history:
    st.info("本裝置尚無測驗紀錄，請先完成至少一輪單字測驗！")
  else:
    st.write(
        f"本機共儲存 **{len(history)}** 次測驗紀錄（依時間由新至舊排列）："
    )

    for h_idx, record in enumerate(reversed(history)):
      round_num = len(history) - h_idx
      score_rate = (record["score"] / record["total"]) * 100

      with st.expander(
          f"第 {round_num} 輪 ｜ 【{record['category']}】 得分："
          f" {record['score']}/{record['total']} ({score_rate:.0f}分) ｜"
          f" {record['time']}"
      ):
        st.caption(
            f"測驗時間：{record['time']} ｜ 題庫類別：{record['category']}"
        )

        for q_idx, q_item in enumerate(record["questions"]):
          is_correct = q_item["is_correct"]
          icon = "✅" if is_correct else "❌"
          st.markdown(f"**第 {q_idx + 1} 題：{q_item['word']}** {icon}")
          st.caption("單字發音：")
          st.audio(get_audio_bytes(q_item["word"]), format="audio/mp3")

          if is_correct:
            st.success(f"正解：{q_item['correct_def']}")
          else:
            st.error(f"你的回答：{q_item['user_choice']}")
            st.success(f"正確解答：{q_item['correct_def']}")
          st.divider()


# ==================== 視圖 4：單字學習與測驗 ====================
else:
  # 階段 1：背誦單字
  if st.session_state.mode == "STUDY":
    idx = st.session_state.study_index
    total = len(st.session_state.selected_words)
    current_word = st.session_state.selected_words[idx]

    st.title(f"📖【{st.session_state.current_category}】單字背誦")
    st.progress((idx + 1) / total)
    st.caption(f"背誦進度：第 {idx + 1} 題 / 共 {total} 題")

    st.subheader(f"單字：**{current_word['word']}**")
    st.caption("🔊 單字發音：")
    st.audio(get_audio_bytes(current_word["word"]), format="audio/mp3")
    st.success(f"釋義：{current_word['def']}")

    if idx + 1 < total:
      if st.button("下一個單字 ➡️", use_container_width=True):
        st.session_state.study_index += 1
        st.rerun()
    else:
      if st.button(
          f"🎉 背誦完成！進入 {total} 題測驗 🚀", use_container_width=True
      ):
        st.session_state.mode = "QUIZ"
        st.rerun()

  # 階段 2：隨機測驗
  elif st.session_state.mode == "QUIZ":
    idx = st.session_state.quiz_step
    total = len(st.session_state.quiz_questions)
    q = st.session_state.quiz_questions[idx]

    st.title(f"📝【{st.session_state.current_category}】單字測驗")
    st.progress((idx + 1) / total)
    st.caption(f"測驗進度：第 {idx + 1} 題 / 共 {total} 題")

    st.subheader(f"請選擇正確釋義： **{q['word']}**")
    st.caption("🔊 題目發音：")
    st.audio(get_audio_bytes(q["word"]), format="audio/mp3")

    for opt in q["options"]:
      if st.button(opt, key=f"quiz_{idx}_{opt}", use_container_width=True):
        is_correct = opt == q["correct_def"]
        is_weakness_test = st.session_state.current_category == "🎯 弱點加強專項"

        if is_correct:
          st.session_state.score += 1
          # 若在「弱點專項測驗」中答對，錯誤次數遞減，歸零直接移除
          if is_weakness_test and q["word"] in st.session_state.wrong_words_db:
            st.session_state.wrong_words_db[q["word"]]["count"] -= 1
            if st.session_state.wrong_words_db[q["word"]]["count"] <= 0:
              del st.session_state.wrong_words_db[q["word"]]
              st.session_state.cleared_words.append(q["word"])
              st.session_state.total_cleared_count += 1
            save_browser_data("wrong_words", st.session_state.wrong_words_db)
        else:
          st.session_state.wrong_answers.append({
              "word": q["word"],
              "correct_def": q["correct_def"],
              "user_choice": opt,
              "example": q["example"],
          })

        st.session_state.current_quiz_records.append({
            "word": q["word"],
            "correct_def": q["correct_def"],
            "user_choice": opt,
            "is_correct": is_correct,
            "example": q["example"],
        })

        if idx + 1 < total:
          st.session_state.quiz_step += 1
        else:
          # 測驗結算：寫入本機歷史紀錄
          new_round = {
              "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
              "category": st.session_state.current_category,
              "score": st.session_state.score,
              "total": total,
              "questions": st.session_state.current_quiz_records,
          }
          st.session_state.quiz_history.append(new_round)
          save_browser_data("quiz_history", st.session_state.quiz_history)

          # 寫入本機弱點庫
          if st.session_state.wrong_answers:
            for w_item in st.session_state.wrong_answers:
              w = w_item["word"]
              if w in st.session_state.wrong_words_db:
                st.session_state.wrong_words_db[w]["count"] += 1
                st.session_state.wrong_words_db[w]["last_wrong_time"] = (
                    datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                )
              else:
                st.session_state.wrong_words_db[w] = {
                    "word": w,
                    "def": w_item["correct_def"],
                    "category": st.session_state.current_category,
                    "example": w_item.get("example", ""),
                    "count": 1,
                    "last_wrong_time": (
                        datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    ),
                }
            save_browser_data("wrong_words", st.session_state.wrong_words_db)

          st.session_state.mode = "RESULT"
        st.rerun()

  # 階段 3：本輪結算
  elif st.session_state.mode == "RESULT":
    total = len(st.session_state.quiz_questions)
    score = st.session_state.score
    rate = (score / total) * 100

    st.balloons()
    st.title(f"🎯 【{st.session_state.current_category}】學習結算")
    st.metric(
        label="測驗成績",
        value=f"{rate:.0f} 分",
        delta=f"答對 {score} / {total} 題",
    )

    if (
        st.session_state.current_category == "🎯 弱點加強專項"
        and st.session_state.cleared_words
    ):
      st.success(
          "🌟 **恭喜攻克弱點！** 以下單字已熟記並成功從弱點加強庫移除："
          f" **{', '.join(st.session_state.cleared_words)}**"
      )

    if st.session_state.wrong_answers:
      st.error(
          f"⚠️ 本輪共答錯 {len(st.session_state.wrong_answers)}"
          " 題，已自動收錄至此裝置的「個人弱點加強庫」！"
      )
      st.subheader("❌ 本輪錯題檢討")
      for item in st.session_state.wrong_answers:
        with st.expander(f"單字：{item['word']}"):
          st.write(f"**正確釋義：** {item['correct_def']}")
          st.write(f"**你的選擇：** {item['user_choice']}")
          st.caption("單字發音：")
          st.audio(get_audio_bytes(item["word"]), format="audio/mp3")
    else:
      st.success("太棒了！5 題全部答對 💯！本次測驗表現完美！")

    col1, col2 = st.columns(2)
    with col1:
      if st.button(
          f"開始下一輪新的 {SESSION_COUNT} 題 🔄", use_container_width=True
      ):
        cat_to_start = (
            selected_category
            if st.session_state.current_category == "🎯 弱點加強專項"
            else st.session_state.current_category
        )
        init_session(cat_to_start, CATEGORIES_DB)
        st.rerun()
    with col2:
      st.caption("💡 此紀錄已安全保存在本裝置瀏覽器中，不與其他裝置共用。")