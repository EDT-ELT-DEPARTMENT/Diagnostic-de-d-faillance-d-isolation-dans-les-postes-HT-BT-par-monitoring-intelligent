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
# Titre du projet d'application actuel
ST_TITRE_OFFICIEL = "Diagnostic des défaillances d’Isolation dans les Postes HT/BT par Monitoring Intelligent du Taux d’Ozone via Automate programmable"
ADMIN_REF = "Diagnostic des défaillances d’Isolation dans les Postes HT/BT par Monitoring Intelligent du Taux d’Ozone via Automate programmable"

# Rappel obligatoire du cadre de déploiement d'origine de la plateforme
FRAMEWORK_EDT = "Plateforme de gestion des EDTs-S2-2026-Département d'Électrotechnique-Faculté de génie électrique-UDL-SBA"

st.set_page_config(
    page_title=ST_TITRE_OFFICIEL,
    layout="wide",
    initial_sidebar_state="expanded"
)

# Rafraîchissement automatique toutes les 2 secondes pour coller au rythme de l'automate
st_autorefresh(interval=2000, key="datarefresh")

# Initialisation persistante du décalage (Offset / Tare) pour le courant de fuite
if 'if_offset' not in st.session_state:
    st.session_state.if_offset = 0.0

# Navigation par menu latéral
st.sidebar.title("📂 Menu Principal")
st.sidebar.markdown(f"**Propulsé par :**\n*{FRAMEWORK_EDT}*")
st.sidebar.divider()
page = st.sidebar.radio("Navigation :", ["📊 Monitoring Temps Réel", "🔬 Prototype & Datasheet"])

# =================================================================
# 2. FONCTIONS DE SERVICE (FIREBASE & PDF)
# =================================================================
@st.cache_resource
def initialiser_firebase():
    """Initialise la connexion Firebase pour récupérer les registres de l'Automate (Modbus TCP / IoT)"""
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

def generer_pdf_datasheet():
    """Génère l'export PDF de la fiche technique basé sur le modèle d'estimation indirecte"""
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", 'B', 14)
    pdf.cell(190, 10, txt="RAPPORT TECHNIQUE - CAPTEUR LOGICIEL O3 VIA COURANT DE FUITE", ln=True, align='C')
    pdf.ln(5)
    
    pdf.set_font("Arial", size=10)
    pdf.cell(190, 8, txt=f"Projet : {ST_TITRE_OFFICIEL}", ln=True)
    pdf.cell(190, 8, txt=f"Framework de Gestion : {FRAMEWORK_EDT}", ln=True)
    pdf.cell(190, 8, txt=f"Date de génération : {datetime.now().strftime('%d/%m/%Y %H:%M')}", ln=True)
    
    pdf.ln(5)
    pdf.set_font("Arial", 'B', 11)
    pdf.cell(190, 8, txt="1. Principe Algorithmique du Soft-Sensing", ln=True)
    pdf.set_font("Arial", size=10)
    pdf.multi_cell(190, 6, txt="Plutôt que de mesurer directement l'ozone gazeux, ce système utilise les registres "
                               "de courant de fuite (mA) acquis par l'automate. L'ozone estimé est déduit via "
                               "la puissance de décharge thermique, pondérée par les lois exponentielles de "
                               "dissociation liées à la température et à l'humidité relative ambiante.")
    return pdf.output(dest='S').encode('latin-1')

# =================================================================
# 3. PAGE 1 : MONITORING TEMPS RÉEL (ESTIMATION & ALERTE)
# =================================================================
if page == "📊 Monitoring Temps Réel":
    st.title("⚡ Soft-Sensing & Diagnostic d'Isolation HT/BT")
    st.markdown(f"### {ST_TITRE_OFFICIEL}")
    st.caption(f"Analyseur rattaché au pôle technique : {FRAMEWORK_EDT}")
    st.info(f"📅 Analyse en direct des cellules au : {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")

    # Initialisation des variables d'environnement et de fuite électrique
    if 'temp_reelle' not in st.session_state: st.session_state.temp_reelle = 25.0
    if 'hum_reelle' not in st.session_state: st.session_state.hum_reelle = 40.0
    if 'courant_fuite' not in st.session_state: st.session_state.courant_fuite = 0.0
    if 'dp_pc' not in st.session_state: st.session_state.dp_pc = 0.0

    with st.sidebar:
        st.header("🎮 Acquisition API & Paramètres")
        mode_experimental = st.toggle("🚀 Mode Automate en Ligne (Live API)", value=True)
        st.divider()
        
        # Définition des constantes du modèle physique d'Ozone
        st.subheader("🎛️ Constantes du Modèle")
        k0 = st.number_input("Facteur d'émission brut ($K_0$)", value=0.150, format="%.3f")
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
                        st.success(f"📳 Données API Synchronisées")
                except Exception as e:
                    st.error(f"⚠️ Erreur liaison Modbus : {e}")
            
            # --- TARE TECHNIQUE DU COURANT DE FUITE ---
            st.subheader("⚖️ Calibrage Ligne")
            if st.button("Fixer le Zéro Absolu (Tare If)"):
                st.session_state.if_offset = st.session_state.courant_fuite
                st.success(f"Zéro fixé à {st.session_state.if_offset} mA")
            
            if st.button("Réinitialiser Tare"):
                st.session_state.if_offset = 0.0
                st.info("Valeur usine restaurée")
        else:
            st.header("💻 Potentiomètres de Simulation")
            st.session_state.courant_fuite = st.slider("Courant de Fuite Mesuré (mA)", 0.0, 10.0, 1.8)
            st.session_state.temp_reelle = st.slider("Température Cellule (°C)", 10.0, 85.0, 25.0)
            st.session_state.hum_reelle = st.slider("Humidité Cellule (%)", 10.0, 95.0, 40.0)
            st.session_state.dp_pc = st.slider("Activité DP Déduite (pC)", 0, 3000, 250)

    # --- MOTEUR DE CALCUL INVERSE (DÉDUCTION DE L'OZONE) ---
    temp_actuelle = st.session_state.temp_reelle
    hum_actuelle = st.session_state.hum_reelle
    
    # Élimination du bruit de fond résistif via la tare logicielle
    if_utile = max(0.0, st.session_state.courant_fuite - st.session_state.if_offset)
    
    # Évaluation des facteurs d'atténuation (Loi d'Arrhenius & Dissociation radicalaire)
    f_T = np.exp(-theta_T * (temp_actuelle - 25.0))
    f_H = np.exp(-theta_H * (hum_actuelle - 40.0))
    
    # Application de l'équation maîtresse de transfert : If -> O3 estimé
    o3_estime = k0 * if_utile * f_T * f_H

    # Évaluation mathématique de l'indice de défaillance global
    indice_brut = (o3_estime * 300) + (if_utile * 10) + (st.session_state.dp_pc * 0.02)
    indice_final = min(100.0, max(0.0, indice_brut))

    # --- LOGIQUE D'ALERTE LOGICIELLE SUR SEUILS OZONE ÉVALUÉS ---
    if o3_estime < 0.05:
        statut_alerte = "🟢 ISOLATION CONFORME (Aucun Risque Détecté)"
        style_bandeau = "normal"
    elif 0.05 <= o3_estime < 0.25:
        statut_alerte = "🟡 VIGILANCE TECHNIQUE (Effet Corona Suspecté - Nettoyer les isolateurs)"
        style_bandeau = "warning"
    else:
        statut_alerte = "🔴 ALERTE CRITIQUE DIÉLECTRIQUE (Décharges Partielles Hautement Destructives)"
        style_bandeau = "danger"

    # --- AFFICHAGE SUR L'INTERFACE UTILISATEUR ---
    st.subheader(f"Mode d'analyse : {'📡 DONNÉES TEMPS RÉEL API' if mode_experimental else '💻 MODÈLE MATHÉMATIQUE SIMULÉ'}")
    
    # Ligne 1 : Grandeurs mesurées directement par l'automate
    col_mesures = st.columns(4)
    col_mesures[0].metric("🔌 Courant de fuite total", f"{st.session_state.courant_fuite:.2f} mA", delta=f"Utile: {if_utile:.2f} mA")
    col_mesures[1].metric("🌡️ Température Ambiante", f"{temp_actuelle:.1f} °C")
    col_mesures[2].metric("💧 Humidité Relative", f"{hum_actuelle:.1f} %")
    col_mesures[3].metric("📊 Mesure Corrélée (DP)", f"{st.session_state.dp_pc:.0f} pC")

    st.markdown("#### 🧪 Synthèse de l'Ozone Déduit par Capteur Logiciel")
    
    # Ligne 2 : Résultats calculés par le modèle
    col_calculs = st.columns(4)
    col_calculs[0].metric("🌀 Taux O₃ Estimé", f"{o3_estime:.3f} ppm", delta="Calculé", delta_color="inverse")
    col_calculs[1].metric("📉 Coef Thermique (f_T)", f"{f_T:.2f}")
    col_calculs[2].metric("💧 Coef Hydrique (f_H)", f"{f_H:.2f}")
    col_calculs[3].metric("🎯 Indice de Sévérité", f"{indice_final:.1f} %")

    # Affichage dynamique du bandeau d'alerte de l'automate
    if style_bandeau == "danger":
        st.error(f"🚨 **ANOMALIE SYSTÈME :** {statut_alerte}")
    elif style_bandeau == "warning":
        st.warning(f"⚠️ **NOTIFICATION AVANT-PANNE :** {statut_alerte}")
    else:
        st.success(f"✅ **ÉTAT DE LA CELLULE :** {statut_alerte}")

    st.divider()

    # --- GRAPHIQUE DE CINÉTIQUE : RÉPONSE DE L'O₃ SELON LE COURANT DE FUITE ---
    if_range = np.linspace(0, 10, 100)
    # Simulation de la courbe O3 = f(If) sous les conditions T et H actuelles
    o3_curve_vals = [k0 * max(0.0, i - st.session_state.if_offset) * f_T * f_H for i in if_range]
    
    fig_prediction = go.Figure()
    fig_prediction.add_trace(go.Scatter(x=if_range, y=o3_curve_vals, name="Courbe de transfert théorique", line=dict(color='yellow', width=3)))
    fig_prediction.add_trace(go.Scatter(x=[if_range[0], if_range[-1]], y=[0.05, 0.05], name="Seuil de Vigilance", line=dict(color='orange', width=1.5, dash='dash')))
    fig_prediction.add_trace(go.Scatter(x=[if_range[0], if_range[-1]], y=[0.25, 0.25], name="Seuil Critique", line=dict(color='red', width=1.5, dash='dot')))
    
    # Point de fonctionnement actuel
    fig_prediction.add_trace(go.Scatter(x=[st.session_state.courant_fuite], y=[o3_estime], name="Point de fonctionnement Actuel", mode='markers', marker=dict(color='magenta', size=12, symbol='cross')))

    fig_prediction.update_layout(
        template="plotly_dark",
        title=f"Abaque Prédictif de l'Ozone en fonction du Courant de Fuite (Pour T={temp_actuelle}°C et H={hum_actuelle}%)",
        xaxis_title="Courant de fuite mesuré (mA)",
        yaxis_title="Taux d'Ozone Déduit (ppm)",
        legend=dict(yanchor="top", y=0.99, xanchor="left", x=0.01)
    )
    st.plotly_chart(fig_prediction, use_container_width=True)

    # --- INFOS COMPLÉMENTAIRES ---
    st.info(f"💡 **Note d'étalonnage :** Le décalage de ligne actuel est configuré à {st.session_state.if_offset} mA. À cette température et humidité, chaque mA additionnel de fuite génère un apport théorique de {k0 * f_T * f_H:.4f} ppm d'O₃.")

# =================================================================
# 4. PAGE 2 : PROTOTYPE & DATASHEET
# =================================================================
elif page == "🔬 Prototype & Datasheet":
    st.title("🔬 Caractéristiques Matérielles & Spécifications du Modèle")
    st.markdown(f"#### {ST_TITRE_OFFICIEL}")
    st.caption(f"Système développé sous l'égide : {FRAMEWORK_EDT}")
    st.divider()

    col_img, col_desc = st.columns([1.5, 1])
    with col_img:
        st.subheader("🖼️ Vue du Dispositif Expérimental")
        try:
            st.image("prototype.jpg", caption="Capteur de courant de fuite torique et automate de traitement.", use_container_width=True)
        except:
            st.error("⚠️ Image de configuration 'prototype.jpg' manquante.")

    with col_desc:
        st.subheader("📝 Fondements Mathématiques")
        st.markdown("L'estimation s'appuie sur la formule physique d'émission et d'atténuation couplée :")
        st.latex(r"[O_3]_{estim\acute{e}} = K_0 \cdot I_{utile} \cdot e^{-\theta_T(T - 25)} \cdot e^{-\theta_H(H - 40)}")
        try:
            pdf_data = generer_pdf_datasheet()
            st.download_button("📥 Exporter le Modèle de Calcul (PDF)", pdf_data, "Modele_Estimation_O3_SBA.pdf", "application/pdf")
        except:
            pass

    st.divider()
    st.subheader("📐 Cartographie Modbus des Registres et Composants de la Plateforme")

    # Tableau global ordonné selon la disposition stricte demandée
    data_tab = {
        "Enseignements": [
            "Estimation de l'O3 gazeux", 
            "Traitement centralisé des alertes", 
            "Acquisition de la dérive de surface", 
            "Suivi de la cinétique thermique", 
            "Mesure de l'activité ionisante",
            "Passerelle Web de Supervision"
        ],
        "Code": [
            "SOFT-O3-ALG", 
            "CPU-1214C-S7", 
            "ROG-MA-100", 
            "DHT22-MB-IND", 
            "HFCT-01-SBA",
            "ETH-GATE-2026"
        ],
        "Enseignants": [
            "Équipe Automatique", 
            "Équipe Électrotechnique", 
            "Équipe Haute Tension", 
            "Équipe Instrumentation", 
            "Équipe Réseaux Électriques",
            "Équipe Informatique Industrielle"
        ],
        "Horaire": [
            "Cycle Réel < 5ms", 
            "Synchrone 10ms", 
            "Continu Permanent", 
            "Échantillonnage 2s", 
            "Capture Crête Rapide",
            "Rafraîchissement 2s"
        ],
        "Jours": [
            "Permanent", 
            "Permanent", 
            "Permanent", 
            "Permanent", 
            "Permanent",
            "Permanent"
        ],
        "Lieu": [
            "Bloc Algorithmique", 
            "Armoire Basse Tension", 
            "Isolateur Haute Tension", 
            "Compartiment Jeux de Barres", 
            "Tête de Câble Arrivée",
            "Serveur Cloud UDL"
        ],
        "Promotion": [
            "M2 Génie Électrique", 
            "M2 Électrotechnique", 
            "M2 Réseaux Électriques", 
            "M2 Instrumentation", 
            "M2 Smart Grids",
            "M2 Informatique"
        ]
    }
    
    st.table(pd.DataFrame(data_tab))

# =================================================================
# 5. PIED DE PAGE INTERACTIF
# =================================================================
st.warning("⚠️ Attention : Les données d'Ozone affichées proviennent d'une inférence logicielle calculée à partir du courant de fuite. Vérifier périodiquement l'état d'étalonnage.")
st.markdown("<hr>", unsafe_allow_html=True)
st.markdown(f"<center><b>{ST_TITRE_OFFICIEL}</b><br><small>Système géré par la structure : {FRAMEWORK_EDT}</small></center>", unsafe_allow_html=True)
