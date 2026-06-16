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
ADMIN_REF = "Diagnostic des défaillances d’Isolation dans les Postes HT/BT par Monitoring Intelligent du Taux d’Ozone via Automate programmable"

st.set_page_config(
    page_title=ST_TITRE_OFFICIEL,
    layout="wide",
    initial_sidebar_state="expanded"
)

# Rafraîchissement automatique toutes les 2 secondes
st_autorefresh(interval=2000, key="datarefresh")

# Initialisation persistante du décalage (Offset) pour le calibrage "Zéro" du capteur d'Ozone
if 'o3_offset' not in st.session_state:
    st.session_state.o3_offset = 0.0

# Navigation par menu latéral
st.sidebar.title("📂 Menu Principal")
page = st.sidebar.radio("Navigation :", ["📊 Monitoring Temps Réel", "🔬 Prototype & Datasheet"])

# =================================================================
# 2. FONCTIONS DE SERVICE (FIREBASE & PDF)
# =================================================================
@st.cache_resource
def initialiser_firebase():
    """Initialise la connexion Firebase pour récupérer les registres de l'Automate"""
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
    """Génère l'export PDF de la fiche technique du système de diagnostic"""
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(190, 10, txt="DATASHEET TECHNIQUE : MONITORING INTELLIGENT HT/BT", ln=True, align='C')
    pdf.ln(10)
    
    pdf.set_font("Arial", size=11)
    pdf.cell(190, 10, txt=f"Projet : {ST_TITRE_OFFICIEL}", ln=True)
    pdf.cell(190, 10, txt=f"Référence Système : {ADMIN_REF}", ln=True)
    pdf.cell(190, 10, txt=f"Date de génération : {datetime.now().strftime('%d/%m/%Y %H:%M')}", ln=True)
    
    pdf.ln(5)
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(190, 10, txt="1. Architecture du Système de Supervision", ln=True)
    pdf.set_font("Arial", size=10)
    pdf.multi_cell(190, 8, txt="Ce système utilise un automate programmable industriel (API) couplé à des "
                               "capteurs de haute précision (Ozone, Température, Humidité) pour détecter "
                               "précocement la dégradation des isolants solides et gazeux (effet corona, "
                               "décharges partielles) au sein des cellules et transformateurs des postes HT/BT.")
    return pdf.output(dest='S').encode('latin-1')

# =================================================================
# 3. PAGE 1 : MONITORING TEMPS RÉEL
# =================================================================
if page == "📊 Monitoring Temps Réel":
    st.title("⚡ Monitoring Intelligent & Diagnostic d'Isolation")
    st.markdown(f"### {ST_TITRE_OFFICIEL}")
    st.info(f"📅 État des cellules HT/BT au : {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")

    # Initialisation des états des variables du Poste HT/BT
    if 'temp_reelle' not in st.session_state: st.session_state.temp_reelle = 25.0
    if 'hum_reelle' not in st.session_state: st.session_state.hum_reelle = 45.0
    if 'o3_reelle' not in st.session_state: st.session_state.o3_reelle = 0.0
    if 'courant_fuite' not in st.session_state: st.session_state.courant_fuite = 0.0
    if 'dp_pc' not in st.session_state: st.session_state.dp_pc = 0.0

    with st.sidebar:
        st.header("🎮 Flux de Données API")
        mode_experimental = st.toggle("🚀 Activer Liaison Automate (Modbus/Liaison API)", value=True)
        st.divider()
        
        if mode_experimental:
            automate_actif = st.selectbox("📡 Modèle d'Automate connecté :", ["Siemens S7-1200 (Modbus TCP)", "Schneider M221 (IoT GW)"])
            fb_path = "/Poste_HT_BT/SiemensS7" if "Siemens" in automate_actif else "/Poste_HT_BT/SchneiderM221"
            
            if initialiser_firebase():
                try:
                    ref = db.reference(fb_path)
                    data_cloud = ref.get()
                    if data_cloud:
                        st.session_state.temp_reelle = float(data_cloud.get('temperature', 25.0))
                        st.session_state.hum_reelle = float(data_cloud.get('humidite', 45.0))
                        
                        # Récupération du registre brute du capteur d'Ozone (ex: conversion AN en ppm)
                        val_o3_raw = int(data_cloud.get('ozone_raw', 0))
                        if val_o3_raw > 0:
                            # Exemple de conversion d'un registre API 12-bits (0-4095) vers une plage 0-5 ppm d'O3
                            st.session_state.o3_reelle = round((val_o3_raw / 4095.0) * 5.0, 3)
                        else:
                            st.session_state.o3_reelle = float(data_cloud.get('ozone_ppm', 0.0))
                        
                        st.session_state.courant_fuite = float(data_cloud.get('courant_fuite_mA', 0.1))
                        st.session_state.dp_pc = float(data_cloud.get('decharges_pC', 0.0))
                        
                        st.success(f"✅ Liaison API Stable ({automate_actif})")
                except Exception as e:
                    st.error(f"❌ Erreur de lecture Registres : {e}")
            
            # --- SECTION CALIBRAGE DU CAPTEUR ---
            st.subheader("⚖️ Calibrage Capteur O₃")
            if st.button("Calibrer le Zéro (Tare O3)"):
                st.session_state.o3_offset = st.session_state.o3_reelle
                st.success(f"Zéro fixé à {st.session_state.o3_offset} ppm")
            
            if st.button("Réinitialiser Calibrage"):
                st.session_state.o3_offset = 0.0
                st.info("Calibrage d'origine restauré")

            st.divider()
            vol_cellule = st.slider("Volume Compartiment (m³)", 1.0, 50.0, 10.0)
            taux_ventilation = st.slider("Renouvellement Air (m³/h)", 0.0, 20.0, 2.0)
        else:
            st.header("💻 Mode Simulation Panne")
            st.session_state.temp_reelle = st.slider("Température Interne T (°C)", 15.0, 90.0, 35.0)
            st.session_state.hum_reelle = st.slider("Humidité Relative H (%)", 5.0, 95.0, 60.0)
            st.session_state.o3_reelle = st.slider("Ozone Brut mesuré (ppm)", 0.0, 2.5, 0.45)
            st.session_state.courant_fuite = st.slider("Courant de fuite surfacique (mA)", 0.0, 10.0, 1.2)
            st.session_state.dp_pc = st.slider("Activité Décharges Partielles (pC)", 0, 5000, 450)
            taux_ventilation = 1.5
            vol_cellule = 8.0

    # --- MOTEUR DE DÉDUCTION DU DIAGNOSTIC D'ISOLATION ---
    temp_actuelle = st.session_state.temp_reelle
    hum_actuelle = st.session_state.hum_reelle
    
    # Facteurs d'impact environnementaux sur la stabilité et la cinétique de l'Ozone
    f_H = np.exp(-0.015 * (hum_actuelle - 40)) if hum_actuelle > 40 else 1.0
    f_T = np.exp(-0.020 * (temp_actuelle - 25)) if temp_actuelle > 25 else 1.0

    # Application de la Tare de calibrage sur l'Ozone mesuré
    o3_utile = max(0.0, st.session_state.o3_reelle - st.session_state.o3_offset)

    # Modélisation mathématique du taux de dégradation estimé
    # L'ozone est généré par l'ionisation de l'air lors des décharges d'isolation
    tau_renouvellement = taux_ventilation / vol_cellule if vol_cellule > 0 else 0
    Indice_Severite = (o3_utile * 300) + (st.session_state.courant_fuite * 25) + (st.session_state.dp_pc * 0.05)
    Indice_Severite_Ajuste = min(100.0, max(0.0, Indice_Severite * f_H * f_T))

    # --- LOGIQUE DE DIAGNOSTIC CRITIQUE AVEC SEUILS ---
    if o3_utile < 0.05:
        etat_isolation = "🟢 NORMAL (Isolation Saine)"
        couleur_alerte = "normal"
    elif 0.05 <= o3_utile < 0.25:
        etat_isolation = "🟡 VIGILANCE (Effet Corona / Dégradation Mineure)"
        couleur_alerte = "warning"
    else:
        etat_isolation = "🔴 CRITIQUE (Décharges Partielles Actives / Risque de Claquage)"
        couleur_alerte = "danger"

    # --- AFFICHAGE MÉTRIQUES ENVIRENNEMENTALES ---
    st.subheader(f"Statut Acquisition : {'📡 MODE AUTOMATE (LIVE)' if mode_experimental else '💻 MODE SIMULATION ANALYTIQUE'}")
    
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Internal Temperature", f"{temp_actuelle:.1f} °C")
    m2.metric("Relative Humidity", f"{hum_actuelle:.1f} %")
    m3.metric("⚡ Courant de fuite", f"{st.session_state.courant_fuite:.2f} mA")
    m4.metric("📊 Activité DP", f"{st.session_state.dp_pc:.0f} pC")

    st.markdown("#### 🔬 Analyse de la Concentration d'Ozone & Sévérité du Diélectrique")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("🌀 Taux O₃ Net (Utile)", f"{o3_utile:.3f} ppm", delta=f"Brut: {st.session_state.o3_reelle:.3f}")
    c2.metric("🌡️ Impact Thermique (f_T)", f"{f_T:.2f}", delta="Atténuation O3")
    c3.metric("💧 Impact Humidité (f_H)", f"{f_H:.2f}", delta="Dissociation O3")
    
    # Affichage de l'état d'isolation déduit
    c4.metric("🎯 Indice de Défaillance", f"{Indice_Severite_Ajuste:.1f} %")

    if couleur_alerte == "danger":
        st.error(f"🚨 **ALERTE CRITIQUE API :** {etat_isolation}")
    elif couleur_alerte == "warning":
        st.warning(f"⚠️ **AVERTISSEMENT API :** {etat_isolation}")
    else:
        st.success(f"✅ **STATUT SYSTÈME :** {etat_isolation}")

    st.divider()
    
    # --- GRAPHIQUE INTERACTIF DE CINÉTIQUE D'ACCUMULATION D'OZONE ---
    v_range = np.linspace(0.1, 15, 100) # Plage de débit de ventilation
    # Courbes déduites d'accumulation stationnaire d'ozone selon le renouvellement d'air
    y_vals_o3_ss = [max(0.01, (o3_utile * 2.5) / (v + 0.1)) for v in v_range]
    y_vals_critique = [0.25 for _ in v_range]
    y_vals_vigilance = [0.05 for _ in v_range]

    fig_q = go.Figure()
    fig_q.add_trace(go.Scatter(x=v_range, y=y_vals_o3_ss, name="Évolution O₃ Stationnaire", line=dict(color='cyan', width=3)))
    fig_q.add_trace(go.Scatter(x=v_range, y=y_vals_critique, name="Seuil Critique (Défaut Majeur)", line=dict(color='red', width=1.5, dash='dash')))
    fig_q.add_trace(go.Scatter(x=v_range, y=y_vals_vigilance, name="Seuil Vigilance (Corona)", line=dict(color='orange', width=1.5, dash='dot')))

    fig_q.update_layout(
        template="plotly_dark", 
        title="Cinétique de concentration d'Ozone en fonction du taux de renouvellement d'air du Poste", 
        xaxis_title="Débit de Ventilation / Renouvellement (m³/h)", 
        yaxis_title="Concentration O₃ Attendue (ppm)",
        legend=dict(yanchor="top", y=0.99, xanchor="right", x=0.99)
    )
    st.plotly_chart(fig_q, use_container_width=True)

    # --- RAPPORT DE PERFORMANCE ET SÉCURITÉ ---
    st.subheader("📊 Bilan Périodique du Diagnostic Diélectrique")
    col_rep1, col_rep2, col_rep3 = st.columns(3)
    
    with col_rep1:
        st.metric("📉 Concentration O₃ résiduelle", f"{o3_utile:.3f} ppm")
    
    with col_rep2:
        st.metric("⏳ Fréquence Échantillonnage API", "0.5 Hz (2s)")
        
    with col_rep3:
        st.metric("🛡️ Niveau de Risque Actuel", "CRITIQUE" if Indice_Severite_Ajuste > 60 else ("MODÉRÉ" if Indice_Severite_Ajuste > 20 else "FAIBLE"))

    st.info(f"💡 **Note Automate :** Décalage de tare mémorisé : {st.session_state.o3_offset} ppm. L'algorithme prédictif estime la défaillance à {Indice_Severite_Ajuste:.1f}% sur la base du ratio de dissociation de l'Ozone sous conditions ambiantes.")

# =================================================================
# 4. PAGE 2 : PROTOTYPE & DATASHEET
# =================================================================
elif page == "🔬 Prototype & Datasheet":
    st.title("🔬 Spécifications de l'Architecture de Monitoring")
    st.markdown(f"#### {ST_TITRE_OFFICIEL}")
    st.divider()

    col_img, col_desc = st.columns([1.6, 1])
    with col_img:
        st.subheader("🖼️ Implantation Automate & Capteurs")
        try:
            st.image("prototype.jpg", caption="Unité de surveillance intelligente de l'Ozone installée en cellule HT/BT.", use_container_width=True)
        except:
            st.error("⚠️ Image d'illustration 'prototype.jpg' non trouvée.")

    with col_desc:
        st.subheader("📝 Documentation d'Intégration")
        st.success("**Principe de détection :** Les décharges électriques partielles cassent les molécules de dioxygène ($O_2$), ce qui engendre une production mesurable d'Ozone ($O_3$). L'automate traite ce signal analogique pour diagnostiquer l'état d'isolation.")
        try:
            pdf_data = generer_pdf_datasheet()
            st.download_button("📥 Télécharger la Fiche Diagnostic (PDF)", pdf_data, "Fiche_Technique_Isolation_O3_SBA.pdf", "application/pdf")
        except: 
            pass

    st.divider()
    st.subheader("📐 Architecture Modbus & Nomenclature des Composants")

    data_tab = {
        "Bloc/Fonction": [
            "Analyse Chimique Gazeuse", 
            "Traitement & Logique API", 
            "Mesure Température/Humidité", 
            "Mesure Courant de Fuite", 
            "Détection Électromagnétique", 
            "Supervision IoT & Passerelle"
        ],
        "Code (Référence)": [
            "O3-SENS-SPEC", 
            "CPU-S7-1214C-DC/DC/DC", 
            "DHT22-IND-Modbus", 
            "ROGOWSKI-SENS-05", 
            "HFCT-PD-SENS", 
            "USR-TCP232-ED2"
        ],
        "Mode et plage de fonctionnement": [
            "Électrochimique 0-5 ppm", 
            "Cycle d'exécution < 2ms", 
            "-40 à +85°C / 0-100%", 
            "0.1 mA à 10 A AC", 
            "Bande passante 1-30 MHz", 
            "Protocole Modbus TCP/MQTT"
        ],
        "Temps de traitement": [
            "Permanent", 
            "Tâche synchrone", 
            "Échantillonnage 2s", 
            "Temps réel continu", 
            "Capture crête instantanée", 
            "Synchro Cloud 2s"
        ],
        "Localisation": [
            "Compartiment Jeux de Barres", 
            "Armoire de Commande Basse Tension", 
            "Cuve Haute Tension", 
            "Prise de terre isolateur", 
            "Tête de câble arrivées HT", 
            "Pupitre de centralisation"
        ],
        "Type de fonctionnement": [
            "Analogique (4-20 mA)", 
            "Automate Programmable", 
            "Numérique RS485", 
            "Inductif passif", 
            "Haute Fréquence", 
            "Réseau Ethernet/IP"
        ]
    }
    st.table(pd.DataFrame(data_tab))

# =================================================================
# 5. PIED DE PAGE
# =================================================================
st.warning("⚠️ Sécurité : Zone Haute Tension (HT/BT). Ne pas intervenir sur l'Automate sans consignation préalable du jeu de barres.")
st.markdown("<hr>", unsafe_allow_html=True)
st.markdown(f"<center><b>{ST_TITRE_OFFICIEL}</b><br><small>{ADMIN_REF}</small></center>", unsafe_allow_html=True)
