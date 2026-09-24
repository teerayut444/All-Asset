import streamlit as st
import streamlit.components.v1 as stc
from bubble_chart import generate_3d_glossy_bubble_chart_html

def render_tab1_bubble_view(df_filtered, is_dark_mode=False, has_active_filters=False):
    """Renders Tab 1: 3D Glossy Bubble Chart View with Metric Toggles."""
    with st.container(key="tab_bubble"):
        st.markdown("""
        <style>
        .st-key-tab1_metric_toggle_container,
        .st-key-tab1_map_color_toggle_container {
            width: auto !important;
            display: inline-flex !important;
            margin-left: auto !important;
            justify-content: flex-end !important;
        }

        .st-key-tab1_metric_toggle_container div[data-testid="stButtonGroup"],
        .st-key-tab1_metric_toggle_container div[role="radiogroup"],
        .st-key-tab1_metric_toggle_container [data-baseweb="button-group"],
        .st-key-tab1_bubble_metric_radio div[data-testid="stButtonGroup"],
        .st-key-tab1_bubble_metric_radio div[role="radiogroup"] {
            background: var(--seg-track-bg, #f1f5f9) !important;
            border: none !important;
            border-radius: 9999px !important;
            padding: 2px !important;
            box-shadow: none !important;
            display: inline-flex !important;
            flex-direction: row !important;
            align-items: center !important;
            gap: 2px !important;
            width: fit-content !important;
        }

        .st-key-tab1_metric_toggle_container button,
        .st-key-tab1_bubble_metric_radio button {
            border: none !important;
            outline: none !important;
            background: transparent !important;
            border-radius: 9999px !important;
            padding: 3px 12px !important;
            min-height: 28px !important;
            font-weight: 600 !important;
            font-size: 0.80rem !important;
            color: var(--seg-inactive-text, #64748b) !important;
            -webkit-text-fill-color: var(--seg-inactive-text, #64748b) !important;
            transition: all 0.22s cubic-bezier(0.16, 1, 0.3, 1) !important;
            cursor: pointer !important;
        }

        .st-key-tab1_metric_toggle_container button:hover,
        .st-key-tab1_bubble_metric_radio button:hover {
            color: #047857 !important;
            -webkit-text-fill-color: #047857 !important;
            background: rgba(16, 185, 129, 0.09) !important;
        }

        .st-key-tab1_metric_toggle_container button[aria-checked="true"],
        .st-key-tab1_bubble_metric_radio button[aria-checked="true"] {
            background: var(--seg-active-bg, rgba(16, 185, 129, 0.14)) !important;
            backdrop-filter: blur(8px) !important;
            -webkit-backdrop-filter: blur(8px) !important;
            color: var(--seg-active-text, #065f46) !important;
            -webkit-text-fill-color: var(--seg-active-text, #065f46) !important;
            border: 1.5px solid var(--seg-active-border, #059669) !important;
            border-radius: 9999px !important;
            box-shadow: var(--seg-active-shadow, 0 0 14px rgba(16, 185, 129, 0.38)) !important;
            font-weight: 700 !important;
        }

        .st-key-tab_bubble {
            margin-top: -14px !important;
        }
        .st-key-tab_bubble div[data-testid="stHorizontalBlock"] {
            margin-bottom: -18px !important;
        }
        .st-key-tab_bubble iframe {
            margin-top: -8px !important;
        }
        </style>
        """, unsafe_allow_html=True)

        _, col_b2 = st.columns([0.65, 0.35])
        with col_b2:
            with st.container(key="tab1_metric_toggle_container"):
                bubble_metric = st.segmented_control(
                    label="bubble_metric",
                    options=[":material/tag: จำนวนทรัพย์สิน", ":material/payments: มูลค่ารวม"],
                    default=":material/tag: จำนวนทรัพย์สิน",
                    key="tab1_bubble_metric_radio",
                    label_visibility="collapsed"
                )
                if not bubble_metric:
                    bubble_metric = ":material/tag: จำนวนทรัพย์สิน"

        # Check cached initial bubble HTML for instant load
        if (not has_active_filters and "cached_bubble_html_v2" in st.session_state and not is_dark_mode and
            bubble_metric == ":material/tag: จำนวนทรัพย์สิน"):
            bubble_html = st.session_state["cached_bubble_html_v2"]
        else:
            bubble_html = generate_3d_glossy_bubble_chart_html(
                df_filtered, 
                bubble_metric=bubble_metric, 
                is_dark_mode=is_dark_mode
            )
        
        try:
            stc.html(bubble_html, height=860)
        except Exception:
            st.html(bubble_html)
