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
FRAMEWORK_EDT = "Diagnostic des défaillances d’Isolation par Monitoring Intelligent Acoustique et Taux d’Ozone via Automate"

st.set_page_config(
    page_title=ST_TITRE_OFFICIEL,
    layout="wide",
    initial_sidebar_state="expanded"
)

st_autorefresh(interval=2000, key="acoustrefresh")

if 'if_offset' not in st.session_state:
    st.session_state.if_offset = 0.0

st.sidebar.title("📂 Menu Principal")
st.sidebar.markdown(f"**Projet de fin d'études :**\n*{FRAMEWORK_EDT}*")
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
# 3. PAGE 1 : MONITORING ACOUSTIQUE & ANALYSE À T=0
# =================================================================
if page == "📊 Monitoring Acoustique":
    st.title("🔊 Plateforme de monitoring d'un poste HT/BT-Sidi Bel Abbès_Diagnostic Instantané à t=0 & Cinétique de Décharges partielles")
    st.markdown(f"### {ST_TITRE_OFFICIEL}")
    st.caption(f"Système de traitement rattaché au pôle : {FRAMEWORK_EDT}")

    if 'temp_reelle' not in st.session_state: st.session_state.temp_reelle = 25.0 
    if 'hum_reelle' not in st.session_state: st.session_state.hum_reelle = 40.0
    if 'courant_fuite' not in st.session_state: st.session_state.courant_fuite = 4.90
    if 'idp_crête' not in st.session_state: st.session_state.idp_crête = 4.88
    if 'freq_ultrasons' not in st.session_state: st.session_state.freq_ultrasons = 40.0

    with st.sidebar:
        st.header("🎮 Paramètres d'Écoute Acoustique")
        mode_experimental = st.toggle("🚀 Mode Capteur Physique en Ligne", value=False)
        st.divider()
        
        st.subheader("⚙️ Coeffs de Production Initiale (t=0)")
        k_acoust = st.number_input("Gain Capteur ($K_{acoustique}$)", value=2.50, format="%.2f")
        f_max_res = st.number_input("Fréquence Max à vide ($f_{max}$ kHz)", value=140.0, format="%.1f")
        
        # Coefficients d'impact sur la GÉNÉRATION PURE à t=0
        alpha_gen = st.number_input("Inhibition Thermique Génération ($\\alpha_{gen}$)", value=0.012, format="%.3f")
        beta_gen = st.number_input("Quenching Humidité Génération ($\\beta_{gen}$)", value=0.018, format="%.3f")
        
        # Coefficient de DECOMPOSITION (pour info comparative t>0)
        theta_decompo = st.number_input("Taux de Décomposition Thermique (t>0)", value=0.035, format="%.3f")
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
            st.session_state.temp_reelle = st.slider("Température ambiante du Poste (°C)", 10.0, 70.0, 18.2)
            st.session_state.hum_reelle = st.slider("Humidité ambiante (%)", 5.0, 95.0, 28.2)

    # --- CALCULS PHYSIQUES QUANTITATIFS ---
    idp = st.session_state.idp_crête
    f_us = st.session_state.freq_ultrasons
    T = st.session_state.temp_reelle
    H = st.session_state.hum_reelle
    
    # Énergie acoustique équivalente
    f_res_dynamique = f_max_res - 60.0 * np.tanh(idp / 3.0)
    amplitude_acoustique = k_acoust * idp * (f_us / 40.0) * np.exp(-((f_us - f_res_dynamique) / 35.0)**2)
    if idp == 0:
        amplitude_acoustique = 0.0

    # FORMULATION : Concentration instantanée générée à t=0
    o3_généré_t0 = 0.5 * amplitude_acoustique * np.exp(-alpha_gen * T) * np.exp(-beta_gen * H)
    
    # Calcul comparatif : Ce qui survit après décomposition thermique (t > 0)
    o3_résiduel = o3_généré_t0 * np.exp(-theta_decompo * max(0.0, T - 20.0))

    indice_final = min(100.0, max(0.0, (amplitude_acoustique * 5) + (st.session_state.courant_fuite * 8)))

    # --- SÉCURITÉ BASÉE SUR L'INTENSITÉ INITIALE ---
    if st.session_state.courant_fuite > 4.5 and amplitude_acoustique == 0.0:
        statut_alerte = "🚨 COURT-CIRCUIT FRANC GALVANIQUE (Liaison solide, aucun plasma gazeux généré)"
        style_bandeau = "danger_cc"
    elif o3_généré_t0 >= 0.20 or amplitude_acoustique > 15.0:
        statut_alerte = "🔴 IONISATION CRITIQUE À L'ORIGINE (La décharge produit une quantité dangereuse d'O₃ à l'instant t=0)"
        style_bandeau = "danger"
    elif (0.04 <= o3_généré_t0 < 0.20) or (5.0 <= amplitude_acoustique <= 15.0):
        statut_alerte = "⚠️ VIGILANCE MICRO-ARCS (Génération d'O₃ détectée à la source)"
        style_bandeau = "warning"
    else:
        statut_alerte = "🟢 ISOLEMENT NORMAL (Énergie d'ionisation négligeable)"
        style_bandeau = "normal"

    # --- PANNEAU DES MESURES ---
    col_mesures = st.columns(5)
    col_mesures[0].metric("🔌 I de fuite (Masse)", f"{st.session_state.courant_fuite:.2f} mA")
    col_mesures[1].metric("⚡ Idp (Impulsion)", f"{idp:.2f} mA")
    col_mesures[2].metric("🔊 Freq Écoute", f"{f_us:.1f} kHz")
    col_mesures[3].metric("🌡️ Température", f"{T:.1f} °C")
    col_mesures[4].metric("💧 Humidité", f"{H:.1f} %")

    st.divider()

    # --- DEUX CADRANS ---
    st.markdown("### 🎛️ Analyse Synoptique de la Décharge (Physique des Arcs)")
    
    col_t0, col_tx, col_metrics = st.columns([3.5, 3.5, 3])
    
    with col_t0:
        max_scale_t0 = max(5.0, float(np.ceil(o3_généré_t0)))
        fig_t0 = go.Figure(go.Indicator(
            mode="gauge+number",
            value=o3_généré_t0,
            domain={'x': [0, 1], 'y': [0, 1]},
            title={'text': "<b>O₃ Instantané Généré (t=0)</b><br><span style='font-size:0.8em;color:#00ffcc'>Concentration brute à la source</span>", 'font': {'size': 14, 'color': '#00ffcc'}},
            gauge={
                'axis': {'range': [0, max_scale_t0], 'tickcolor': "white"},
                'bar': {'color': "#00ffcc"},
                'bgcolor': "rgba(0,0,0,0)",
                'steps': [
                    {'range': [0, 0.04], 'color': 'rgba(0, 200, 100, 0.2)'},      
                    {'range': [0.04, 0.20], 'color': 'rgba(250, 150, 0, 0.3)'},    
                    {'range': [0.20, max_scale_t0], 'color': 'rgba(230, 0, 50, 0.4)'}  
                ]
            }
        ))
        fig_t0.update_layout(template="plotly_dark", paper_bgcolor='rgba(0,0,0,0)', height=270, margin=dict(l=20, r=20, t=60, b=10))
        st.plotly_chart(fig_t0, use_container_width=True)

    with col_tx:
        max_scale_tx = max(5.0, float(np.ceil(o3_résiduel)))
        fig_tx = go.Figure(go.Indicator(
            mode="gauge+number",
            value=o3_résiduel,
            domain={'x': [0, 1], 'y': [0, 1]},
            title={'text': "<b>O₃ Résiduel Stable (t>0)</b><br><span style='font-size:0.8em;color:#ffaa00'>Valeur résiduelle dans la cellule</span>", 'font': {'size': 14, 'color': '#ffaa00'}},
            gauge={
                'axis': {'range': [0, max_scale_tx], 'tickcolor': "white"},
                'bar': {'color': "#ffaa00"},
                'bgcolor': "rgba(0,0,0,0)",
                'steps': [
                    {'range': [0, 0.04], 'color': 'rgba(0, 200, 100, 0.1)'},      
                    {'range': [0.04, 0.20], 'color': 'rgba(250, 150, 0, 0.1)'},    
                    {'range': [0.20, max_scale_tx], 'color': 'rgba(230, 0, 50, 0.1)'}  
                ]
            }
        ))
        fig_tx.update_layout(template="plotly_dark", paper_bgcolor='rgba(0,0,0,0)', height=270, margin=dict(l=20, r=20, t=60, b=10))
        st.plotly_chart(fig_tx, use_container_width=True)

    with col_metrics:
        st.markdown("<br>", unsafe_allow_html=True)
        st.metric("🔊 Amplitude Acoustique", f"{amplitude_acoustique:.2f} µV")
        st.metric("🎯 Résonance Plasma", f"{f_res_dynamique:.1f} kHz")
        st.metric("🚨 Taux de Sévérité", f"{indice_final:.1f} %")
        
        if style_bandeau == "danger_cc":
            st.error(f"⚡ {statut_alerte}")
        elif style_bandeau == "danger":
            st.error(f"🚨 {statut_alerte}")
        elif style_bandeau == "warning":
            st.warning(f"⚠️ {statut_alerte}")
        else:
            st.success(f"✅ {statut_alerte}")

    st.divider()

    # --- SPECTRE ACOUSTIQUE ---
    f_axis = np.linspace(20, 180, 200)
    spectre_vals = k_acoust * idp * (f_axis / 40.0) * np.exp(-((f_axis - f_res_dynamique) / 35.0)**2) if idp > 0 else np.zeros_like(f_axis)

    fig_spectre = go.Figure()
    fig_spectre.add_trace(go.Scatter(x=f_axis, y=spectre_vals, name="Spectre d'Émission Acoustique", line=dict(color='orange', width=3)))
    fig_spectre.add_trace(go.Scatter(x=[f_us], y=[amplitude_acoustique], name="Point d'Écoute Actuel", mode='markers', marker=dict(color='red', size=12, symbol='cross')))
    fig_spectre.update_layout(template="plotly_dark", title="Spectre fréquentiel de la Décharge Partielle", xaxis_title="Fréquence (kHz)", yaxis_title="Amplitude (µV)")
    st.plotly_chart(fig_spectre, use_container_width=True)

# =================================================================
# 4. PAGE 2 : PROTOTYPE & DATASHEET (RESTRUCTURATION DES EN-TÊTES)
# =================================================================
elif page == "🔬 Prototype & Datasheet":
    st.title("🔬 Structure d'Implantation Industrielle & Registres")
    st.markdown(f"#### {ST_TITRE_OFFICIEL}")
    st.caption(f"Fichier configuré et opéré sous l'autorité de : {FRAMEWORK_EDT}")
    st.divider()

    # Chargement de l'image de l'architecture du transformateur HT/BT
    st.image(
        "prototype-2.png", 
        caption="Schéma structurel d'implantation du transformateur cible HT/BT - Point d'analyse d'isolement", 
        use_container_width=True
    )
    st.divider()

    # Remplacement des entêtes EDT obsolètes par la cartographie des télémesures industrielles
    data_tab = {
        "Grandeurs & Fonctions Diagnostic": [
            "Analyse Spectrale et Transformée de Fourier Ultrasons",
            "Couplage Électro-Acoustique de la Décharge (Idp vs f_us)",
            "Discrimination Acoustique du Court-circuit franc",
            "Modélisation de l'Ozone à t=0 (Cinétique de Synthèse Co-dépendante)"
        ],
        "Code Variable / ID": [
            "AC-SPECT-FFT",
            "COUPL-IDP-FUS",
            "DETEC-SILENCE",
            "O3-INSTANT-T0"
        ],
        "Module Automate / Équipe": [
            "Équipe Instrumentation",
            "Équipe Automatique",
            "Équipe Haute Tension",
            "Équipe Électrotechnique"
        ],
        "Cadence de Scrutation": [
            "Cycle API 2ms",
            "Instantané continu",
            "Filtrage 5ms",
            "Échantillonnage t=0"
        ],
        "Régime d'Acquisition": [
            "Permanent",
            "Permanent",
            "Permanent",
            "Permanent"
        ],
        "Unité Matérielle / Implantation": [
            "Processeur DSP Filtre",
            "Unité Centrale CPU",
            "Module d'entrée Analogique",
            "Chambre de décharge / Éclateur"
        ],
        "Classe de Supervision": [
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
st.markdown(f"<center><small>Application de Monitoring Industriel : <b>{FRAMEWORK_EDT}</b></small></center>", unsafe_allow_html=True)
