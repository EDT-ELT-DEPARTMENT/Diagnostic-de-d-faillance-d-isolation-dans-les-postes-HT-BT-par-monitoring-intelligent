import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from datetime import datetime
import firebase_admin
from firebase_admin import credentials, db
from streamlit_autorefresh import st_autorefresh

# =================================================================
# 1. CONFIGURATION DE LA PAGE & TITRES OFFICIELS
# =================================================================
ST_TITRE_OFFICIEL = "Diagnostic des défaillances d’Isolation par Monitoring Intelligent Acoustique et Taux d’Ozone via Automate"
FRAMEWORK_EDT = "Diagnostic de défaillance d'isolation dans les postes HT/BT par monitoring intelligent du taux d'ozone via automate programmable"

st.set_page_config(
    page_title=ST_TITRE_OFFICIEL,
    layout="wide",
    initial_sidebar_state="expanded"
)

# Rafraîchissement automatique de l'IHM toutes les 2 secondes
st_autorefresh(interval=2000, key="acoustrefresh")

if 'if_offset' not in st.session_state:
    st.session_state.if_offset = 0.0

st.sidebar.title("📂 Menu Principal")
st.sidebar.markdown(f"**Propulsé par :**\n*{FRAMEWORK_EDT}*")
st.sidebar.divider()
page = st.sidebar.radio("Navigation :", ["📊 Monitoring Acoustique", "🔬 Prototype & Datasheet"])

# =================================================================
# 2. LIAISON COMPOSANT CLOUD (FACULTATIVE)
# =================================================================
@st.cache_resource
def initialiser_firebase():
    try:
        if not firebase_admin._apps:
            if "firebase" in st.secrets:
                fb_secrets = dict(st.secrets["firebase"])
                if "private_key" in fb_secrets:
                    fb_secrets["private_key"] = fb_secrets["private_key"].replace("\\n", "\n")
                cred = credentials.Certificate(fb_secrets)
            else:
                cred = credentials.Certificate("votre-cle.json")
                
            firebase_admin.initialize_app(cred, {
                'databaseURL': 'https://oh-generator-plasma-sba-default-rtdb.europe-west1.firebasedatabase.app'
            })
        return True
    except Exception as e:
        st.sidebar.error(f"Erreur Automate : {e}")
        return False

# =================================================================
# 3. PAGE 1 : MONITORING ACOUSTIQUE & CADRAN GRADUÉ
# =================================================================
if page == "📊 Monitoring Acoustique":
    st.title("🔊 Diagnostic Acoustique & Indicateurs de Performance")
    st.markdown(f"### {ST_TITRE_OFFICIEL}")
    st.caption(f"Système de traitement rattaché au pôle : {FRAMEWORK_EDT}")

    if 'temp_reelle' not in st.session_state: st.session_state.temp_reelle = 18.2
    if 'hum_reelle' not in st.session_state: st.session_state.hum_reelle = 28.2
    if 'courant_fuite' not in st.session_state: st.session_state.courant_fuite = 4.90
    if 'idp_crête' not in st.session_state: st.session_state.idp_crête = 4.88
    if 'freq_ultrasons' not in st.session_state: st.session_state.freq_ultrasons = 40.0

    with st.sidebar:
        st.header("🎮 Paramètres d'Écoute Acoustique")
        mode_experimental = st.toggle("🚀 Mode Capteur Physique en Ligne", value=False)
        st.divider()
        
        st.subheader("⚙️ Constantes Plasma & Piézo")
        k_acoust = st.number_input("Gain Capteur ($K_{acoustique}$)", value=2.50, format="%.2f")
        f_max_res = st.number_input("Fréquence Max à vide ($f_{max}$ kHz)", value=140.0, format="%.1f")
        theta_T = st.number_input("Atténuation Thermique O3 ($\\theta_T$)", value=0.020, format="%.3f")
        theta_H = st.number_input("Atténuation Humidité O3 ($\\theta_H$)", value=0.015, format="%.3f")
        st.divider()
        
        if mode_experimental:
            if initialiser_firebase():
                try:
                    ref = db.reference("/Poste_HT_BT/AcousticSensor")
                    data_cloud = ref.get()
                    if data_cloud:
                        st.session_state.temp_reelle = float(data_cloud.get('temperature', 25.0))
                        st.session_state.hum_reelle = float(data_cloud.get('humidite', 40.0))
                        st.session_state.courant_fuite = float(data_cloud.get('courant_fuite_mA', 0.0))
                        st.session_state.idp_crête = float(data_cloud.get('idp_mA', 0.0))
                        st.session_state.freq_ultrasons = float(data_cloud.get('freq_kHz', 40.0))
                except Exception as e:
                    st.sidebar.error(f"Erreur de lecture bus : {e}")
        else:
            st.header("💻 Simulateur d'Énergie Acoustique")
            st.session_state.courant_fuite = st.slider("Courant Globale de Fuite (mA)", 0.0, 15.0, 4.90)
            st.session_state.idp_crête = st.slider("Amplitude Courant de Décharge Idp (mA)", 0.0, 10.0, 4.88)
            st.session_state.freq_ultrasons = st.slider("Fréquence centrale captée (kHz)", 20.0, 180.0, 40.0)
            st.session_state.temp_reelle = st.slider("Température ambiante (°C)", 10.0, 70.0, 18.2)
            st.session_state.hum_reelle = st.slider("Humidité ambiante (%)", 5.0, 95.0, 28.2)

    # --- CALCULS PHYSIQUES ---
    idp = st.session_state.idp_crête
    f_us = st.session_state.freq_ultrasons
    temp_actuelle = st.session_state.temp_reelle
    hum_actuelle = st.session_state.hum_reelle
    
    f_res_dynamique = f_max_res - 60.0 * np.tanh(idp / 3.0)
    amplitude_acoustique = k_acoust * idp * (f_us / 40.0) * np.exp(-((f_us - f_res_dynamique) / 35.0)**2)
    if idp == 0:
        amplitude_acoustique = 0.0

    f_T = np.exp(-theta_T * (temp_actuelle - 25.0))
    f_H = np.exp(-theta_H * (hum_actuelle - 40.0))
    o3_estime = 0.25 * amplitude_acoustique * f_T * f_H

    indice_final = min(100.0, max(0.0, (amplitude_acoustique * 5) + (st.session_state.courant_fuite * 8)))

    # --- LOGIQUE D'ANALYSE DUAL (ACOUSTIQUE + O3) ---
    if st.session_state.courant_fuite > 4.5 and amplitude_acoustique == 0.0:
        statut_alerte = "🚨 COURT-CIRCUIT FRANC GALVANIQUE (Courant élevé, silence acoustique complet : pas d'arcs dans l'air)"
        style_bandeau = "danger_cc"
    elif o3_estime >= 0.25 or amplitude_acoustique > 15.0:
        statut_alerte = "🔴 ALERTE CRITIQUE DIÉLECTRIQUE & CHIMIQUE (Forte accumulation d'O₃ ou forte intensité acoustique)"
        style_bandeau = "danger"
    elif (0.05 <= o3_estime < 0.25) or (5.0 <= amplitude_acoustique <= 15.0):
        statut_alerte = "⚠️ VIGILANCE MICRO-ARCS (Activité ultrasonore modérée ou Effet Corona suspecté)"
        style_bandeau = "warning"
    else:
        statut_alerte = "🟢 ISOLEMENT SAIN (Niveau de bruit de fond normal)"
        style_bandeau = "normal"

    # --- AFFICHAGE DES VALEURS BRUTES ---
    col_mesures = st.columns(5)
    col_mesures[0].metric("🔌 I de fuite (Masse)", f"{st.session_state.courant_fuite:.2f} mA")
    col_mesures[1].metric("⚡ Idp (Impulsion)", f"{idp:.2f} mA")
    col_mesures[2].metric("🔊 Freq Écoute", f"{f_us:.1f} kHz")
    col_mesures[3].metric("🌡️ Température", f"{temp_actuelle:.1f} °C")
    col_mesures[4].metric("💧 Humidité", f"{hum_actuelle:.1f} %")

    st.divider()

    # --- DISPOSITION GRAPHIQUE COMPACTE : CADRAN + METRICS RÉSULTATS ---
    st.markdown("### 🎛️ Tableau de Bord Inférence & Diagnostic")
    
    col_gauche, col_droite = st.columns([4, 6])
    
    with col_gauche:
        max_scale = max(5.0, float(np.ceil(o3_estime)))
        
        # FIX : Suppression de 'bold': True qui causait le crash de l'app. Remplacement par les balises HTML <b>...</b>
        fig_gauge = go.Figure(go.Indicator(
            mode="gauge+number",
            value=o3_estime,
            domain={'x': [0, 1], 'y': [0, 1]},
            title={'text': "<b>Taux O₃ Estimé (ppm)</b>", 'font': {'size': 20, 'color': '#00ffcc'}},
            gauge={
                'axis': {'range': [0, max_scale], 'tickwidth': 2, 'tickcolor': "white"},
                'bar': {'color': "rgba(255, 255, 255, 0.8)", 'thickness': 0.25},
                'bgcolor': "rgba(0,0,0,0)",
                'borderwidth': 2,
                'bordercolor': "#444",
                'steps': [
                    {'range': [0, 0.05], 'color': 'rgba(0, 200, 100, 0.3)'},      
                    {'range': [0.05, 0.25], 'color': 'rgba(250, 150, 0, 0.4)'},    
                    {'range': [0.25, max_scale], 'color': 'rgba(230, 0, 50, 0.4)'}  
                ],
                'threshold': {
                    'line': {'color': "#00ffcc", 'width': 4},
                    'thickness': 0.8,
                    'value': o3_estime
                }
            }
        ))
        
        fig_gauge.update_layout(
            template="plotly_dark",
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            height=320,
            margin=dict(l=30, r=30, t=60, b=10)
        )
        st.plotly_chart(fig_gauge, use_container_width=True)

    with col_droite:
        st.markdown("<br>", unsafe_allow_html=True)
        col_sub_calc = st.columns(2)
        col_sub_calc[0].metric("🔊 Amplitude Acoustique", f"{amplitude_acoustique:.2f} µV")
        col_sub_calc[1].metric("🎯 Fréquence Résonance", f"{f_res_dynamique:.1f} kHz")
        
        st.markdown("<br>", unsafe_allow_html=True)
        st.metric("🚨 Sévérité Système", f"{indice_final:.1f} %")
        
        if style_bandeau == "danger_cc":
            st.error(f"⚡ **CRITIQUE :** {statut_alerte}")
        elif style_bandeau == "danger":
            st.error(f"🚨 **DANGER DE DÉGRADATION :** {statut_alerte}")
        elif style_bandeau == "warning":
            st.warning(f"⚠️ **AVERTISSEMENT :** {statut_alerte}")
        else:
            st.success(f"✅ **STATUT :** {statut_alerte}")

    st.divider()

    # --- SPECTRE FREQUENTIEL ---
    f_axis = np.linspace(20, 180, 200)
    spectre_vals = k_acoust * idp * (f_axis / 40.0) * np.exp(-((f_axis - f_res_dynamique) / 35.0)**2) if idp > 0 else np.zeros_like(f_axis)

    fig_spectre = go.Figure()
    fig_spectre.add_trace(go.Scatter(x=f_axis, y=spectre_vals, name="Spectre d'Émission Acoustique", line=dict(color='orange', width=3)))
    fig_spectre.add_trace(go.Scatter(x=[f_us], y=[amplitude_acoustique], name="Point d'Écoute Actuel", mode='markers', marker=dict(color='red', size=12, symbol='cross')))
    
    fig_spectre.update_layout(
        template="plotly_dark",
        title="Spectre fréquentiel de la Décharge Partielle (Amplitude mécanique = f(Fréquence))",
        xaxis_title="Fréquence Ultrasons (kHz)",
        yaxis_title="Amplitude du signal capteur (µV)"
    )
    st.plotly_chart(fig_spectre, use_container_width=True)

    # --- SURFACE 3D ---
    st.subheader("🌐 Cartographie Tridimensionnelle de Stabilité Chimique de l'Ozone")
    t_space = np.linspace(10, 70, 30)
    h_space = np.linspace(5, 95, 30)
    T_mesh, H_mesh = np.meshgrid(t_space, h_space)
    
    Z_O3 = 0.25 * amplitude_acoustique * np.exp(-theta_T * (T_mesh - 25.0)) * np.exp(-theta_H * (H_mesh - 40.0))

    fig_3d = go.Figure(data=[go.Surface(x=t_space, y=h_space, z=Z_O3, colorscale='Cividis')])
    fig_3d.add_trace(go.Scatter3d(x=[temp_actuelle], y=[hum_actuelle], z=[o3_estime], mode='markers', marker=dict(size=8, color='magenta')))
    fig_3d.update_layout(
        template="plotly_dark",
        scene=dict(xaxis_title='Température (°C)', yaxis_title='Humidité (%)', zaxis_title='O3 (ppm)'),
        margin=dict(l=0, r=0, b=0, t=40), height=500
    )
    st.plotly_chart(fig_3d, use_container_width=True)

# =================================================================
# 4. PAGE 2 : PROTOTYPE & DATASHEET (DISPOSITION EXIGÉE CONSERVÉE)
# =================================================================
elif page == "🔬 Prototype & Datasheet":
    st.title("🔬 Structure d'Implantation Industrielle & Registres")
    st.markdown(f"#### {ST_TITRE_OFFICIEL}")
    st.caption(f"Fichier configuré et opéré sous l'autorité de : {FRAMEWORK_EDT}")
    st.divider()

    # Ordre strict : Enseignements, Code, Enseignants, Horaire, Jours, Lieu, Promotion
    data_tab = {
        "Enseignements": [
            "Analyse Spectrale et Transformée de Fourier Ultrasons",
            "Couplage Électro-Acoustique de la Décharge (Idp vs f_us)",
            "Discrimination Acoustique du Court-circuit franc",
            "Étude d'atténuation d'ondes de pression en milieu saharien"
        ],
        "Code": [
            "AC-SPECT-FFT",
            "COUPL-IDP-FUS",
            "DETEC-SILENCE",
            "PROP-SAH-40K"
        ],
        "Enseignants": [
            "Équipe Instrumentation",
            "Équipe Automatique",
            "Équipe Haute Tension",
            "Équipe Électrotechnique"
        ],
        "Horaire": [
            "Cycle API 2ms",
            "Instantané continu",
            "Filtrage 5ms",
            "Échantillonnage 2s"
        ],
        "Jours": [
            "Permanent",
            "Permanent",
            "Permanent",
            "Permanent"
        ],
        "Lieu": [
            "Processeur DSP Filtre",
            "Unité Centrale CPU",
            "Module d'entrée Analogique",
            "Cuve Transfo / Isolation"
        ],
        "Promotion": [
            "M2 Instrumentation",
            "M2 Génie Électrique",
            "M2 Réseaux Électriques",
            "M2 Smart Grids"
        ]
    }
    st.table(pd.DataFrame(data_tab))

# =================================================================
# 5. PIED DE PAGE INTERACTIF
# =================================================================
st.markdown("<hr>", unsafe_allow_html=True)
st.markdown(f"<center><small>Application : <b>{FRAMEWORK_EDT}</b></small></center>", unsafe_allow_html=True)
