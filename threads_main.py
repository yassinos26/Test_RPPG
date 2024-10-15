import cv2, os, numpy as np
from fastapi.middleware.cors import CORSMiddleware
from fastapi import FastAPI, File, UploadFile, Form
from face import detect_face, filter_by_confidence
from concurrent.futures import ThreadPoolExecutor
from metrics import (calculate_activity, calculate_sleep, calculate_equilibrium,
                    calculate_metabolism, calculate_health, calculate_relaxation)
from vitals import (bandpass_filter, calculate_heart_rate, calculate_hrv, calculate_stress_level,
                    calculate_blood_pressure, calculate_spo2, verify_signal_strength, calculate_respiration_rate)

# Paramètres de capture
fs = 15  # Fréquence d'échantillonnage (frames par seconde)
lowcut = 0.85  # Fréquence de coupure basse (Hz)
highcut = 2.5  # Fréquence de coupure haute (Hz)
order = 4  # Ordre du filtre
frame_idx = []

# Limites des frames pour calculer différents signaux vitaux
max_frame_HR = 500
max_frame_HRV = 510
max_frame_respiration = 520
max_frame_SPO2 = 530
max_frame_pressions = 540
max_frame_total = 600  # Limite pour les frames totales

# Initialisation de l'application FastAPI
app = FastAPI()

# Liste des origines autorisées
allowed_origins = ["http://localhost:8001"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
)

# Initialisation du détecteur de visage en utilisant le modèle Haar Cascade
face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')

# Dossier pour stocker les vidéos téléchargées
UPLOAD_FOLDER = 'uploads/'
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)  # Créer le dossier s'il n'existe pas

# Variables pour stocker les signaux RGB et RPPG
signals = {"rppg_signal": [], "heart_rates": [], "spo2_rates": [], "hrv_rates": [],
        "respiration_rates": [], "systolic_rates": [], "diastolic_rates": [],
        "ppg_red_signal": [], "ppg_infra_signal": []}

# Variables moyennes et actuelles pour les signaux physiologiques
metrics = {"avg_bpm": 0, "bpm": 0, "avg_hrv": 0, "hrv": 0,
        "avg_spo2": 0, "spo2": 0, "avg_respiration": 0, "respiration": 0,
        "avg_diastolic": 0, "diastolic": 0, "avg_systolic": 0, "systolic": 0}

# Variables pour stocker les scores calculés
scores = {"activity_score": 0, "sleep_score": 0, "equilibrium_score": 0,
        "metabolism_score": 0, "health_score": 0, "relaxation_score": 0}

# Fonction pour réinitialiser les signaux si le nombre de frames dépasse une limite
def reset_signals_if_exceeds():
    global frame_idx, signals, metrics
    signals = {key: [] for key in signals}
    metrics = {key: 0 for key in metrics}
    frame_idx = []

# ThreadPoolExecutor pour exécuter des tâches en parallèle
executor = ThreadPoolExecutor(max_workers=4)

stress_level_label = ''
# Fonction de traitement des métriques vitaux
def process_vital_metrics(face_roi):
    global stress_level_label 
    if face_roi is not None:
        roi_rgb = cv2.cvtColor(face_roi, cv2.COLOR_BGR2RGB)  # Convertir en RGB
        avg_color = np.mean(roi_rgb, axis=(0, 1))  # Moyenne des canaux R, G, B
        signals["rppg_signal"].append(avg_color[1])  # Utiliser le canal vert

        avg_red = np.mean(roi_rgb[:, :, 0])  # Moyenne du canal rouge
        avg_infra = 0.3 * avg_red + 0.59 * avg_color[1] + 0.11 * np.mean(roi_rgb[:, :, 2])  # Signal infrarouge
        signals["ppg_red_signal"].append(avg_red)  # Signal rouge
        signals["ppg_infra_signal"].append(avg_infra)  # Signal infrarouge

        if len(signals["rppg_signal"]) > 27:
            filtered_signal = bandpass_filter(signals["rppg_signal"], lowcut, highcut, fs, order)
            bpm, peak_intervals, peaks = calculate_heart_rate(filtered_signal, fs)
            signals["heart_rates"].append(bpm)
            metrics["avg_bpm"] = round(np.mean(signals["heart_rates"]), 2) if len(signals["heart_rates"]) >= max_frame_HR else metrics["avg_bpm"]

            if verify_signal_strength(signals["ppg_red_signal"]) and verify_signal_strength(signals["ppg_infra_signal"]):
                spo2 = calculate_spo2(signals["ppg_red_signal"], signals["ppg_infra_signal"], fs)
                signals["spo2_rates"].append(spo2)
                metrics["avg_spo2"] = round(np.mean(signals["spo2_rates"]), 2) if len(signals["spo2_rates"]) >= max_frame_SPO2 else metrics["avg_spo2"]

            if len(peaks) > 1:
                _, hrv, _ = calculate_hrv(peaks)
                signals["hrv_rates"].append(hrv)
                metrics["avg_hrv"] = round(np.mean(signals["hrv_rates"]), 2) if len(signals["hrv_rates"]) >= max_frame_HRV else metrics["avg_hrv"]
            
            # Déterminer le niveau de stress
            stress_level_label = calculate_stress_level(peak_intervals)
            
            respiration = calculate_respiration_rate(filtered_signal, fs)
            signals["respiration_rates"].append(respiration)
            metrics["avg_respiration"] = round(np.mean(signals["respiration_rates"]), 2) if len(signals["respiration_rates"]) >= max_frame_respiration else metrics["avg_respiration"]

            systolic, diastolic = calculate_blood_pressure(peak_intervals)
            if systolic and diastolic:
                signals["systolic_rates"].append(systolic)
                signals["diastolic_rates"].append(diastolic)
                metrics["avg_systolic"] = round(np.mean(signals["systolic_rates"]), 2) if len(signals["systolic_rates"]) >= max_frame_pressions else metrics["avg_systolic"]
                metrics["avg_diastolic"] = round(np.mean(signals["diastolic_rates"]), 2) if len(signals["diastolic_rates"]) >= max_frame_pressions else metrics["avg_diastolic"]

# Route pour télécharger et traiter la vidéo
@app.post("/upload_video")
async def upload_video(age: int = Form(...), weight: int = Form(...), height: int = Form(...), video: UploadFile = File(...)):
    global stress_level_label 
    global signals, metrics, scores, frame_idx
    
    # Sauvegarder la vidéo temporairement
    video_path = os.path.join(UPLOAD_FOLDER, video.filename)
    print('Le chemin de la vidéo est :', video_path)

    reset_signals_if_exceeds()  # Réinitialiser les signaux
    
    with open(video_path, "wb") as buffer:
        buffer.write(await video.read())
        
    cap = cv2.VideoCapture(video_path)

    if not cap.isOpened():
        print("Erreur lors du chargement de la vidéo.")
        return {"message": "Erreur lors du chargement de la vidéo"}

    futures = []
    
    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break
        frame_idx.append(len(frame_idx) + 1)

        face_roi, _, _, w, h = detect_face(frame)
        if face_roi is not None:
            is_confident, _ = filter_by_confidence(w, h, frame.shape, threshold=8)
            if is_confident:
                futures.append(executor.submit(process_vital_metrics, face_roi))

    cap.release()

    for future in futures:
        future.result()  # Attendre que toutes les tâches soient terminées

    if len(signals["rppg_signal"]) > max_frame_total:
        scores["activity_score"] = calculate_activity(metrics["avg_bpm"], age)
        scores["sleep_score"] = calculate_sleep(metrics["avg_hrv"], metrics["avg_respiration"])
        scores["equilibrium_score"] = calculate_equilibrium(metrics["avg_hrv"], metrics["avg_systolic"], metrics["avg_diastolic"])
        scores["metabolism_score"] = calculate_metabolism(weight, height, age)
        scores["health_score"] = calculate_health(metrics["avg_spo2"], metrics["avg_bpm"], metrics["avg_systolic"])
        scores["relaxation_score"] = calculate_relaxation(metrics["avg_hrv"], metrics["avg_respiration"])
    
    os.remove(video_path)
        
    # Retourner les résultats
    return {"message": "Vidéo et données reçues avec succès",
        "age": age,
        "weight": weight,
        "height": height,
        "evaluation_HR": metrics["avg_bpm"],
        "evaluation_HRV": metrics["avg_hrv"],
        "evaluation_Spo2": metrics["avg_spo2"],
        "evaluation_respiration": metrics["avg_respiration"],
        "evaluation_diastolic": metrics["avg_diastolic"],
        "evaluation_systolic": metrics["avg_systolic"],
        "evaluation_stress": stress_level_label,
        "evaluation_activity": scores["activity_score"],
        "evaluation_sleep": scores["sleep_score"],
        "evaluation_equilibre": scores["equilibrium_score"],
        "evaluation_metabolism": scores["metabolism_score"],
        "evaluation_health": scores["health_score"],
        "evaluation_relaxation": scores["relaxation_score"]}