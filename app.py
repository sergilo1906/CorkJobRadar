import streamlit as st
from corkjobradar.db import Database
from corkjobradar.runtime_ui import bootstrap
from corkjobradar.ui.shell import render

st.set_page_config(page_title='Cork Job Radar',page_icon=':mag:',layout='wide',initial_sidebar_state='auto')
db=Database()
bootstrap(db)
render(db)
