import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from datetime import datetime
import firebase_admin
from firebase_admin import credentials, db
from streamlit_autorefresh import st_autorefresh
from fpdf import FPDF

# =================================================================
# 1. CONFIGURATION DE LA PAGE & TITRES OFFICIELS
# =================================================================
ST_TITRE_OFFICIEL = "Diagnostic des défaillances d’Isolation dans les Postes HT/BT par Monitoring Intelligent du Taux d’Ozone via Automate programmable"
FRAMEWORK_EDT = "Plateforme de gestion des EDTs-S2-2026-Département d'Électrotechnique-Faculté de génie électrique-UDL-SBA"

st.set_page_config(
    page_title=ST_TITRE_OFFICIEL,
    layout="wide",
    initial_sidebar_state="expanded"
)

# Rafraîchissement automatique de la plateforme toutes les 2 secondes
st_autorefresh(interval=2000, key="datarefresh")

if 'if_offset' not in st.session_state:
    st.session_state.if_offset = 0.0

st.sidebar.title("📂 Menu Principal")
st.sidebar.markdown(f"**Propulsé par :**\n*{FRAMEWORK_EDT}*")
st.sidebar.divider()
page = st.sidebar.radio("Navigation :", ["📊 Monitoring Temps Réel", "🔬 Prototype & Datasheet"])

# =================================================================
# 2. FONCTIONS DE SERVICE
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
        st.sidebar.error(f"Erreur de liaison Cloud Automate : {e}")
        return False

# =================================================================
# 3. PAGE 1 : MONITORING TEMPS RÉEL
# =================================================================
if page == "📊 Monitoring Temps Réel":
    st.title("⚡ Soft-Sensing Avancé & Cartographie Environnementale 3D")
    st.markdown(f"### {ST_TITRE_OFFICIEL}")
    st.caption(f"Analyseur rattaché au pôle technique : {FRAMEWORK_EDT}")

    if 'temp_reelle' not in st.session_state: st.session_state.temp_reelle = 25.0
    if 'hum_reelle' not in st.session_state: st.session_state.hum_reelle = 40.0
    if 'courant_fuite' not in st.session_state: st.session_state.courant_fuite = 0.0
    if 'dp_pc' not in st.session_state: st.session_state.dp_pc = 0.0

    with st.sidebar:
        st.header("🎮 Configuration de l'Automate")
        mode_experimental = st.toggle("🚀 Mode Automate en Ligne (Live API)", value=False)
        st.divider()
        
        st.subheader("🎛️ Constantes de Dissociation")
        k0 = st.number_input("Facteur d'émission brut ($K_0$)", value=0.150, format="%.3f")
        k_dp = st.number_input("Seuil d'activation DP ($K_{dp}$)", value=100.0, format="%.1f")
        theta_T = st.number_input("Dégradation Thermique ($\\theta_T$)", value=0.020, format="%.3f")
        theta_H = st.number_input("Dégradation Humidité ($\\theta_H$)", value=0.015, format="%.3f")
        st.divider()
        
        if mode_experimental:
            automate_actif = st.selectbox("📡 Liaison Automate active :", ["Siemens S7-1200 (Modbus)", "Schneider M221 (IoT)"])
            fb_path = "/Poste_HT_BT/SiemensS7" if "Siemens" in automate_actif else "/Poste_HT_BT/SchneiderM221"
            if initialiser_firebase():
                try:
                    ref = db.reference(fb_path)
                    data_cloud = ref.get()
                    if data_cloud:
                        st.session_state.temp_reelle = float(data_cloud.get('temperature', 25.0))
                        st.session_state.hum_reelle = float(data_cloud.get('humidite', 40.0))
                        st.session_state.courant_fuite = float(data_cloud.get('courant_fuite_mA', 0.0))
                        st.session_state.dp_pc = float(data_cloud.get('decharges_pC', 0.0))
                except Exception as e:
                    st.sidebar.error(f"Erreur Modbus : {e}")
        else:
            st.header("💻 Simulateur de Défauts")
            st.session_state.courant_fuite = st.slider("Courant de Fuite Mesuré (mA)", 0.0, 15.0, 5.0)
            st.session_state.dp_pc = st.slider("Activité Décharges Partielles (pC)", 0, 3000, 500)
            st.session_state.temp_reelle = st.slider("Température Cellule active (°C)", 10.0, 70.0, 25.0)
            st.session_state.hum_reelle = st.slider("Humidité Cellule active (%)", 5.0, 95.0, 40.0)

    # --- ALGORITHME DE CORRÉLATION ---
    temp_actuelle = st.session_state.temp_reelle
    hum_actuelle = st.session_state.hum_reelle
    dp_actuelle = st.session_state.dp_pc
    if_utile = max(0.0, st.session_state.courant_fuite - st.session_state.if_offset)
    
    # Sécurité Court-circuit franc (f_ion = 0 si aucune étincelle dans l'air)
    if dp_actuelle > 0:
        f_ion = dp_actuelle / (dp_actuelle + k_dp)
    else:
        f_ion = 0.0

    # Facteurs de décomposition de l'O3
    f_T = np.exp(-theta_T * (temp_actuelle - 25.0))
    f_H = np.exp(-theta_H * (hum_actuelle - 40.0))
    
    # Taux d'O3 calculé
    o3_estime = k0 * if_utile * f_ion * f_T * f_H

    # Calcul de l'indice de risque global
    indice_brut = (o3_estime * 300) + (if_utile * 10) + (dp_actuelle * 0.02)
    indice_final = min(100.0, max(0.0, indice_brut))

    # Logique de tri des alarmes
    if if_utile > 4.0 and dp_actuelle == 0:
        statut_alerte = "🚨 COURT-CIRCUIT FRANC DÉTECTÉ (Pas d'ionisation d'air - Pas d'Ozone)"
        style_bandeau = "danger_cc"
    elif o3_estime < 0.05:
        statut_alerte = "🟢 ISOLATION CONFORME (Aucun Risque Gazeux)"
        style_bandeau = "normal"
    elif 0.05 <= o3_estime < 0.25:
        statut_alerte = "🟡 VIGILANCE TECHNIQUE (Effet Corona Suspecté)"
        style_bandeau = "warning"
    else:
        statut_alerte = "🔴 ALERTE CRITIQUE DIÉLECTRIQUE (Forte production d'O₃)"
        style_bandeau = "danger"

    # --- AFFICHAGE DES MESURES ---
    col_mesures = st.columns(4)
    col_mesures[0].metric("🔌 Courant de fuite", f"{st.session_state.courant_fuite:.2f} mA")
    col_mesures[1].metric("⚡ Décharges Partielles", f"{dp_actuelle:.0f} pC")
    col_mesures[2].metric("🌡️ Température Image", f"{temp_actuelle:.1f} °C")
    col_mesures[3].metric("💧 Humidité Image", f"{hum_actuelle:.1f} %")

    st.markdown("### 🌀 Diagnostic du Capteur Logiciel")
    col_calc = st.columns(3)
    col_calc[0].metric("🧪 Taux O₃ Estimé", f"{o3_estime:.3f} ppm")
    col_calc[1].metric("⚙️ Coef global d'atténuation", f"{(f_T * f_H):.3f}", help="Plus ce coefficient est proche de 0, plus l'environnement détruit l'ozone rapidement.")
    col_calc[2].metric("🎯 Indice de Sévérité", f"{indice_final:.1f} %")

    if style_bandeau == "danger_cc":
        st.error(f"⚡ **DANGER EXTRÊME :** {statut_alerte}")
    elif style_bandeau == "danger":
        st.error(f"🚨 **ALERTE SYSTÈME :** {statut_alerte}")
    elif style_bandeau == "warning":
        st.warning(f"⚠️ **NOTIFICATION :** {statut_alerte}")
    else:
        st.success(f"✅ **STATUT :** {statut_alerte}")

    st.divider()

    # --- ZONE DE VISUALISATION DE LA DÉPENDANCE DE O3 = f(T, H) ---
    st.subheader("🌐 Cartographie 3D de la Dépendance Environnementale de l'Ozone")
    st.markdown("Ce graphique modélise la stabilité de l'ozone pour le courant de fuite et l'activité de décharge actuels. **Faites pivoter la surface** pour analyser la zone saharienne (Haute Température / Basse Humidité) par rapport aux zones tempérées.")

    # Génération de la matrice de données pour la surface 3D
    t_space = np.linspace(10, 70, 40)  # Axe X : Température de 10 à 70°C
    h_space = np.linspace(5, 95, 40)   # Axe Y : Humidité de 5 à 95%
    T_mesh, H_mesh = np.meshgrid(t_space, h_space)
    
    # Application de la formule sur toute la grille matricielle
    Z_O3 = k0 * if_utile * f_ion * np.exp(-theta_T * (T_mesh - 25.0)) * np.exp(-theta_H * (H_mesh - 40.0))

    # Construction du graphique de surface Plotly
    fig_3d = go.Figure(data=[go.Surface(
        x=t_space,
        y=h_space,
        z=Z_O3,
        colorscale='Viridis',
        colorbar_title="O3 (ppm)"
    )])

    # Ajout du marqueur représentant le point de fonctionnement instantané du poste
    fig_3d.add_trace(go.Scatter3d(
        x=[temp_actuelle],
        y=[hum_actuelle],
        z=[o3_estime],
        mode='markers',
        marker=dict(size=10, color='red', symbol='diamond', line=dict(color='black', width=2)),
        name="Point Actuel"
    ))

    fig_3d.update_layout(
        title=f"Évolution du Taux d'O₃ en fonction de T et H (Pour If = {if_utile:.2f} mA)",
        template="plotly_dark",
        scene=dict(
            xaxis_title='Température (°C)',
            yaxis_title='Humidité (%)',
            zaxis_title='O3 Estimé (ppm)',
            camera=dict(eye=dict(x=1.5, y=1.5, z=1.2))  # Angle de vue initial optimisé
        ),
        margin=dict(l=0, r=0, b=0, t=40),
        height=600
    )
    
    st.plotly_chart(fig_3d, use_container_width=True)

# =================================================================
# 4. PAGE 2 : PROTOTYPE & DATASHEET (DISPOSITION STRICTE DEMANDÉE)
# =================================================================
elif page == "🔬 Prototype & Datasheet":
    st.title("🔬 Registres de Modélisation et Matrice d'Implantation")
    st.markdown(f"#### {ST_TITRE_OFFICIEL}")
    st.caption(f"Structure de déploiement réglementaire : {FRAMEWORK_EDT}")
    st.divider()

    st.subheader("📊 Matrice d'Affectation Technique des Modules de Calcul")

    # Tableau ordonné selon la disposition stricte exigée :
    # Enseignements, Code, Enseignants, Horaire, Jours, Lieu, Promotion
    data_tab = {
        "Enseignements": [
            "Modélisation Tridimensionnelle f(T,H)",
            "Validation Discriminante Courant/O3", 
            "Filtrage mathématique du Court-circuit franc", 
            "Surveillance hydrique et thermique saharienne"
        ],
        "Code": [
            "O3-3D-SURF",
            "CC-FRANC-PROT", 
            "F-ION-ALG-03", 
            "SAH-ENV-CORR"
        ],
        "Enseignants": [
            "Équipe Instrumentation",
            "Équipe Haute Tension", 
            "Équipe Automatique", 
            "Équipe Électrotechnique"
        ],
        "Horaire": [
            "Rafraîchissement 2s",
            "Instantané < 2ms", 
            "Cycle API 5ms", 
            "Échantillonnage 2s"
        ],
        "Jours": [
            "Permanent",
            "Permanent", 
            "Permanent", 
            "Permanent"
        ],
        "Lieu": [
            "Bloc Graphique IHM",
            "Unité Centrale CPU", 
            "Bloc Inférence Logicielle", 
            "Compartiment Jeux de Barres"
        ],
        "Promotion": [
            "M2 Smart Grids",
            "M2 Réseaux Électriques", 
            "M2 Génie Électrique", 
            "M2 Instrumentation"
        ]
    }
    st.table(pd.DataFrame(data_tab))

# =================================================================
# 5. PIED DE PAGE INTERACTIF
# =================================================================
st.markdown("<hr>", unsafe_allow_html=True)
st.markdown(f"<center><small>Application opérée sous l'autorité de : <b>{FRAMEWORK_EDT}</b></small></center>", unsafe_allow_html=True)
