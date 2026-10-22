from pathlib import Path
import streamlit as st
from .visibility import PAGES
from .model import load_view
from . import pages


def render(db):
    st.markdown('<style>'+Path(__file__).with_name('styles.css').read_text(encoding='utf-8')+'</style>',unsafe_allow_html=True)
    with st.sidebar:
        st.markdown('<div class="cjr-brand">Cork Job Radar</div>',unsafe_allow_html=True)
        st.caption('Tu búsqueda IT, en un solo lugar')
        st.radio('Navegación',PAGES,key='ui_area',label_visibility='collapsed',on_change=pages.clear_job)
        st.markdown('<div class="cjr-rule"></div><span class="cjr-status">AutoApply · LIVE OFF</span>',unsafe_allow_html=True)
        st.caption('Local en Windows · Sin coche propio')
    # An explicitly labelled native menu remains usable on narrow screens, without
    # requiring the user to discover Streamlit's icon-only collapsed sidebar.
    st.session_state.ui_mobile_area=st.session_state.get('ui_area',PAGES[0])
    def mobile_changed():
        st.session_state.ui_area=st.session_state.ui_mobile_area
        pages.clear_job()
    with st.container(key='mobile_navigation'):
        st.selectbox('Ir a sección',PAGES,key='ui_mobile_area',on_change=mobile_changed)
    view=load_view(db)
    funcs=dict(zip(PAGES,[pages.home,pages.offers,pages.applications,pages.autoapply,pages.activity,pages.profile]))
    funcs[st.session_state.get('ui_area',PAGES[0])](db,view)
