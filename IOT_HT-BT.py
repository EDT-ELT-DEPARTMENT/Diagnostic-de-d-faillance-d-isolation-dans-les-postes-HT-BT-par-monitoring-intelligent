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
FRAMEWORK_EDT = "Plateforme de gestion des EDTs-S2-2026-Département d'Électrotechnique-Faculté de génie électrique-UDL-SBA"

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
# 3. PAGE 1 : MONITORING ACOUSTIQUE & DÉPENDANCE DE L'OZONE
# =================================================================
if page == "📊 Monitoring Acoustique":
    st.title("🔊 Diagnostic Acoustique (Ultrasons 40-150 kHz) & Inférence O₃")
    st.markdown(f"### {ST_TITRE_OFFICIEL}")
    st.caption(f"Système de traitement rattaché au pôle : {FRAMEWORK_EDT}")

    if 'temp_reelle' not in st.session_state: st.session_state.temp_reelle = 25.0
    if 'hum_reelle' not in st.session_state: st.session_state.hum_reelle = 40.0
    if 'courant_fuite' not in st.session_state: st.session_state.courant_fuite = 0.0
    if 'idp_crête' not in st.session_state: st.session_state.idp_crête = 0.0
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
            st.session_state.courant_fuite = st.slider("Courant Globale de Fuite (mA)", 0.0, 15.0, 4.2)
            st.session_state.idp_crête = st.slider("Amplitude Courant de Décharge Idp (mA)", 0.0, 10.0, 1.5, help="Intensité pure du canal de l'étincelle")
            st.session_state.freq_ultrasons = st.slider("Fréquence centrale captée (kHz)", 20.0, 180.0, 40.0, help="Fréquence d'écoute du microphone piézoélectrique")
            st.session_state.temp_reelle = st.slider("Température ambiante (°C)", 10.0, 70.0, 41.5)
            st.session_state.hum_reelle = st.slider("Humidité ambiante (%)", 5.0, 95.0, 55.0)

    # --- CALCULS PHYSIQUES DES VALEURS ACOUSTIQUES ---
    idp = st.session_state.idp_crête
    f_us = st.session_state.freq_ultrasons
    temp_actuelle = st.session_state.temp_reelle
    hum_actuelle = st.session_state.hum_reelle
    
    # 1. Calcul de la résonance dynamique du plasma (Glissement de fréquence)
    f_res_dynamique = f_max_res - 60.0 * np.tanh(idp / 3.0)
    
    # 2. Calcul de l'amplitude acoustique reçue (Formule de couplage mécanique)
    amplitude_acoustique = k_acoust * idp * (f_us / 40.0) * np.exp(-((f_us - f_res_dynamique) / 35.0)**2)
    if idp == 0:
        amplitude_acoustique = 0.0  # Sécurité court-circuit franc métallique sans bruit de décharge

    # 3. Évaluation de la génération d'ozone induite par l'énergie acoustique utile
    f_T = np.exp(-theta_T * (temp_actuelle - 25.0))
    f_H = np.exp(-theta_H * (hum_actuelle - 40.0))
    
    # L'ozone dépend directement de la puissance acoustique émise (proportionalité de l'ionisation)
    o3_estime = 0.02 * amplitude_acoustique * f_T * f_H

    # Indice de sévérité globale
    indice_final = min(100.0, max(0.0, (amplitude_acoustique * 5) + (st.session_state.courant_fuite * 8)))

    # --- LOGIQUE D'ANALYSE DU FLUX ---
    if st.session_state.courant_fuite > 5.0 and amplitude_acoustique == 0.0:
        statut_alerte = "🚨 COURT-CIRCUIT FRANC GALVANIQUE (Courant élevé, silence acoustique complet : pas d'arcs dans l'air)"
        style_bandeau = "danger_cc"
    elif amplitude_acoustique > 15.0:
        statut_alerte = "🔴 DANGER DISRUPTIF MAJEUR (Forte intensité acoustique : amorçage ou cheminement en cours)"
        style_bandeau = "danger"
    elif 5.0 <= amplitude_acoustique <= 15.0:
        statut_alerte = "⚠️ VIGILANCE MICRO-ARCS (Activité ultrasonore détectée, début d'altération de l'isolant)"
        style_bandeau = "warning"
    else:
        statut_alerte = "🟢 ISOLEMENT SAIN (Niveau de bruit de fond normal)"
        style_bandeau = "normal"

    # --- RENDER DES COMPOSANTS GRAPHIQUES ---
    col_mesures = st.columns(5)
    col_mesures[0].metric("🔌 I de fuite (Masse)", f"{st.session_state.courant_fuite:.2f} mA")
    col_mesures[1].metric("⚡ Idp (Impulsion)", f"{idp:.2f} mA")
    col_mesures[2].metric("🔊 Freq Écoute", f"{f_us:.1f} kHz")
    col_mesures[3].metric("🌡️ Température", f"{temp_actuelle:.1f} °C")
    col_mesures[4].metric("💧 Humidité", f"{hum_actuelle:.1f} %")

    st.markdown("### 🔍 Résultats du Traitement de Signal Acoustique")
    col_calc = st.columns(4)
    col_calc[0].metric("🔊 Amplitude Acoustique", f"{amplitude_acoustique:.2f} µV")
    col_calc[1].metric("🎯 Fréquence Résonance", f"{f_res_dynamique:.1f} kHz")
    col_calc[2].metric("🧪 Taux O₃ Estimé", f"{o3_estime:.3f} ppm")
    col_calc[3].metric("🚨 Sévérité Système", f"{indice_final:.1f} %")

    if style_bandeau == "danger_cc":
        st.error(f"⚡ **CRITIQUE :** {statut_alerte}")
    elif style_bandeau == "danger":
        st.error(f"🚨 **ALERTE :** {statut_alerte}")
    elif style_bandeau == "warning":
        st.warning(f"⚠️ **AVERTISSEMENT :** {statut_alerte}")
    else:
        st.success(f"✅ **STATUT :** {statut_alerte}")

    st.divider()

    # --- GRAPHIC 1: SPECTRE EN FRÉQUENCE DE L'ONDE ACOUSTIQUE ---
    f_axis = np.linspace(20, 180, 200)
    # Re-calcul de la courbe spectrale pour l'Idp sélectionné
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

    # --- GRAPHIC 2: SURFACE 3D DEPENDANCE DE L'OZONE ---
    st.subheader("🌐 Cartographie Tridimensionnelle de Stabilité Chimique de l'Ozone")
    t_space = np.linspace(10, 70, 30)
    h_space = np.linspace(5, 95, 30)
    T_mesh, H_mesh = np.meshgrid(t_space, h_space)
    
    # Calcul matriciel de l'O3
    Z_O3 = 0.02 * amplitude_acoustique * np.exp(-theta_T * (T_mesh - 25.0)) * np.exp(-theta_H * (H_mesh - 40.0))

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

    # Disposition stricte respectée à la lettre : Enseignements, Code, Enseignants, Horaire, Jours, Lieu, Promotion
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
