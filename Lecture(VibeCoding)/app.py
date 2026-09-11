"""쇼핑 리스트 — Streamlit 단일 페이지 앱.

3단계: 기능(FR-1 ~ FR-7)은 그대로 두고 화면을 다듬는다.

상태 변경은 모두 위젯 콜백(on_click / on_change)에서 처리한다.
콜백은 스크립트 본문보다 먼저 실행되므로 st.rerun() 없이도 화면이
항상 최신 상태로 그려진다.

목록은 app.py 옆의 items.json에 저장한다. 브라우저를 새로고침하면
Streamlit 세션이 새로 만들어지므로, 파일에 두지 않으면 목록이 사라진다.
"""

import html
import json
import os
import tempfile
from pathlib import Path

import streamlit as st

DATA_FILE = Path(__file__).parent / "items.json"

st.set_page_config(page_title="쇼핑 리스트", page_icon="🛒")

# 색을 직접 지정하지 않는다. 취소선 항목은 opacity로만 흐리게 해서
# 라이트/다크 테마 어느 쪽에서도 글자가 읽히게 한다.
st.markdown(
    """
    <style>
      /* 본문 폭을 읽기 좋은 정도로 제한 */
      div[data-testid="stMainBlockContainer"] { max-width: 640px; }
      /* 항목 행 사이 간격을 촘촘하고 일정하게 */
      div[data-testid="stVerticalBlock"] { gap: 0.4rem; }
      /* 긴 이름은 줄바꿈해서 버튼을 밀어내지 않게 */
      .item { word-break: break-word; line-height: 1.5; }
      .item.done { text-decoration: line-through; opacity: 0.55; }
    </style>
    """,
    unsafe_allow_html=True,
)


# ---------------------------------------------------------------- 저장소

def load_data():
    """items.json에서 목록을 읽는다 (FR-6).

    파일이 없거나 깨졌으면 빈 목록으로 시작한다. 장보기 메모 하나 때문에
    앱이 아예 뜨지 않는 편보다 낫다.
    """
    try:
        with open(DATA_FILE, encoding="utf-8") as f:
            data = json.load(f)
        items = [
            {"id": int(row["id"]), "name": str(row["name"]), "done": bool(row["done"])}
            for row in data["items"]
        ]
    except (OSError, ValueError, KeyError, TypeError):
        return [], 1
    next_id = max((item["id"] for item in items), default=0) + 1
    return items, next_id


def save_data():
    """현재 목록을 items.json에 쓴다 (FR-6).

    임시 파일에 쓴 뒤 교체해, 쓰는 도중 앱이 죽어도 기존 파일이 깨지지 않게 한다.
    """
    payload = {"items": st.session_state.shopping_items}
    fd, tmp_path = tempfile.mkstemp(dir=str(DATA_FILE.parent), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        os.replace(tmp_path, DATA_FILE)
    except OSError:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
        st.session_state.flash = "목록을 저장하지 못했습니다. 파일 권한을 확인해 주세요."


# ---------------------------------------------------------------- 상태

def init_state():
    """세션 상태를 최초 1회만 초기화한다 (PRD 7장 데이터 모델).

    항목 리스트의 키는 반드시 shopping_items다. st.session_state.items는
    SessionState의 items() 메서드와 충돌해 리스트 대신 메서드가 잡힌다.
    """
    if "shopping_items" not in st.session_state:
        # 각 항목: {"id": int, "name": str, "done": bool}
        items, next_id = load_data()
        st.session_state.shopping_items = items
        st.session_state.next_id = next_id
    if "editing_id" not in st.session_state:
        st.session_state.editing_id = None
    if "confirm_reset" not in st.session_state:
        st.session_state.confirm_reset = False
    if "flash" not in st.session_state:
        # 콜백 안에서는 st.warning이 그려지지 않으므로 메시지를 담아 뒀다가
        # 본문에서 한 번 출력하고 비운다.
        st.session_state.flash = None


def find_item(item_id):
    """id로 항목을 찾는다. 없으면 None."""
    for item in st.session_state.shopping_items:
        if item["id"] == item_id:
            return item
    return None


def validate_name(raw, exclude_id=None):
    """이름을 다듬고 검증한다. (정리된_이름, 오류메시지) 중 하나만 채워 반환.

    exclude_id는 수정 중인 항목의 id. 자기 자신의 이름은 중복으로 보지 않는다.
    """
    name = (raw or "").strip()
    if not name:
        return None, "항목 이름을 입력해 주세요."
    for item in st.session_state.shopping_items:
        if item["id"] != exclude_id and item["name"] == name:
            return None, f"'{name}'은(는) 이미 목록에 있습니다."
    return name, None


# ---------------------------------------------------------------- 기능

def add_item():
    """입력창의 값을 새 항목으로 목록 맨 아래에 추가한다 (FR-1)."""
    name, error = validate_name(st.session_state.new_item)
    if error:
        st.session_state.flash = error
        return
    st.session_state.shopping_items.append(
        {"id": st.session_state.next_id, "name": name, "done": False}
    )
    st.session_state.next_id += 1
    st.session_state.new_item = ""  # 입력창 비우기
    save_data()


def start_edit(item_id):
    """해당 항목을 수정 모드로 전환한다 (FR-2). 동시에 하나만 가능."""
    st.session_state.editing_id = item_id


def cancel_edit():
    """수정을 취소하고 원래 이름을 유지한다 (FR-2)."""
    st.session_state.editing_id = None


def update_item(item_id):
    """수정 입력창의 값으로 항목 이름을 바꾼다 (FR-2). done 상태는 유지."""
    item = find_item(item_id)
    if item is None:
        st.session_state.editing_id = None
        return
    name, error = validate_name(st.session_state[f"edit_{item_id}"], exclude_id=item_id)
    if error:
        st.session_state.flash = error
        return  # 수정 모드 유지
    item["name"] = name
    st.session_state.editing_id = None
    save_data()


def delete_item(item_id):
    """항목 하나를 즉시 삭제한다 (FR-3). 확인창은 두지 않는다."""
    st.session_state.shopping_items = [
        item for item in st.session_state.shopping_items if item["id"] != item_id
    ]
    if st.session_state.editing_id == item_id:
        st.session_state.editing_id = None
    save_data()


def toggle_item(item_id):
    """체크박스 상태를 항목에 반영한다 (FR-4)."""
    item = find_item(item_id)
    if item is not None:
        item["done"] = st.session_state[f"chk_{item_id}"]
        save_data()


def clear_completed():
    """done=True인 항목을 일괄 삭제한다 (FR-3)."""
    removed_ids = {
        item["id"] for item in st.session_state.shopping_items if item["done"]
    }
    st.session_state.shopping_items = [
        item for item in st.session_state.shopping_items if not item["done"]
    ]
    if st.session_state.editing_id in removed_ids:
        st.session_state.editing_id = None
    save_data()


def ask_reset():
    """초기화 확인 단계로 들어간다 (FR-7)."""
    st.session_state.confirm_reset = True


def cancel_reset():
    """초기화를 그만둔다 (FR-7)."""
    st.session_state.confirm_reset = False


def reset_all():
    """목록 전체와 저장 파일을 비운다 (FR-7). 되돌릴 수 없다."""
    # 사라진 항목의 체크박스 위젯 상태가 남아 새 항목에 딸려가지 않도록 함께 지운다
    for key in [k for k in st.session_state if str(k).startswith("chk_")]:
        del st.session_state[key]
    st.session_state.shopping_items = []
    st.session_state.next_id = 1
    st.session_state.editing_id = None
    st.session_state.confirm_reset = False
    st.session_state.flash = None
    try:
        DATA_FILE.unlink(missing_ok=True)
    except OSError:
        save_data()  # 지우지 못하면 최소한 빈 목록으로 덮어쓴다


# ---------------------------------------------------------------- 화면

init_state()

st.title("🛒 쇼핑 리스트")

# 입력창 + 추가 버튼 — Enter(on_change)와 버튼(on_click) 모두 add_item으로
input_col, button_col = st.columns([5, 1], vertical_alignment="bottom")
with input_col:
    st.text_input(
        "항목 입력",
        key="new_item",
        placeholder="무엇을 살까요?",
        label_visibility="collapsed",
        on_change=add_item,
    )
with button_col:
    st.button("추가", key="add", on_click=add_item, width="stretch")

if st.session_state.flash:
    st.warning(st.session_state.flash)
    st.session_state.flash = None  # 일회성: 다음 조작에는 남지 않는다

# 진행 상황
items = st.session_state.shopping_items
total = len(items)
done = sum(1 for item in items if item["done"])
st.caption(f"완료 {done} / 전체 {total}")
st.progress(done / total if total else 0.0)  # 항목이 없을 때 0으로 나누지 않도록

if total > 0 and done == total:
    st.success("장보기 완료! 🎉")

st.divider()

# 항목 목록
if not items:
    st.info("아직 항목이 없습니다. 위에서 추가해 보세요.", icon="🛒")  # FR-5
else:
    for item in items:
        item_id = item["id"]
        editing = st.session_state.editing_id == item_id
        # 수정 모드의 [저장][취소]는 아이콘보다 넓어야 글자가 잘리지 않는다
        spec = [0.5, 5.4, 1.2, 1.2] if editing else [0.5, 7, 0.9, 0.9]
        check_col, name_col, edit_col, delete_col = st.columns(
            spec, vertical_alignment="center"
        )

        # 체크박스 상태는 위젯 key가 곧 진실이므로 최초 1회만 항목값으로 심는다
        chk_key = f"chk_{item_id}"
        if chk_key not in st.session_state:
            st.session_state[chk_key] = item["done"]

        if editing:
            # 수정 모드 행
            with check_col:
                st.checkbox("완료", key=chk_key, label_visibility="collapsed",
                            disabled=True)
            with name_col:
                st.text_input("이름 수정", value=item["name"], key=f"edit_{item_id}",
                              label_visibility="collapsed")
            with edit_col:
                st.button("저장", key=f"save_{item_id}", width="stretch",
                          on_click=update_item, args=(item_id,))
            with delete_col:
                st.button("취소", key=f"cancel_{item_id}", width="stretch",
                          on_click=cancel_edit)
        else:
            with check_col:
                st.checkbox("완료", key=chk_key, label_visibility="collapsed",
                            help="구매 완료", on_change=toggle_item, args=(item_id,))
            with name_col:
                # 이름은 사용자 입력이므로 반드시 이스케이프한다
                css_class = "item done" if item["done"] else "item"
                st.markdown(
                    f'<span class="{css_class}">{html.escape(item["name"])}</span>',
                    unsafe_allow_html=True,
                )
            with edit_col:
                st.button("✏️", key=f"editbtn_{item_id}", help="수정", width="stretch",
                          on_click=start_edit, args=(item_id,))
            with delete_col:
                st.button("🗑️", key=f"del_{item_id}", help="삭제", width="stretch",
                          on_click=delete_item, args=(item_id,))

st.divider()

# 정리 버튼 — 초기화는 되돌릴 수 없으므로 확인 단계를 둔다 (FR-7)
clear_col, reset_col, _ = st.columns([1.4, 1.2, 2.4])
with clear_col:
    st.button("완료 항목 삭제", key="clear_done", disabled=(done == 0),
              help="체크한 항목을 한 번에 지웁니다", width="stretch",
              on_click=clear_completed)
with reset_col:
    st.button("전체 초기화", key="reset", disabled=(total == 0),
              help="목록을 모두 지웁니다", width="stretch", on_click=ask_reset)

if st.session_state.confirm_reset:
    st.warning(f"항목 {total}개를 모두 지웁니다. 되돌릴 수 없습니다.")
    yes_col, no_col, _ = st.columns([1, 1, 3])
    with yes_col:
        st.button("초기화", key="reset_yes", type="primary", width="stretch",
                  on_click=reset_all)
    with no_col:
        st.button("취소", key="reset_no", width="stretch", on_click=cancel_reset)
