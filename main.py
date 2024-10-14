import cv2, os, numpy as np
from fastapi.middleware.cors import CORSMiddleware
from fastapi import FastAPI , File , UploadFile , Form
from face import detect_face , filter_by_confidence
# from concurrent.futures import ThreadPoolExecutor , as_completed
from metrics import (calculate_activity , calculate_sleep , calculate_equilibrium ,
                    calculate_metabolism , calculate_health , calculate_relaxation)
from vitals import (bandpass_filter, calculate_heart_rate, calculate_hrv, calculate_stress_level, calculate_blood_pressure,
                    calculate_spo2, verify_signal_strength, calculate_respiration_rate)

# Paramètres de capture
fs = 30  # Fréquence d'échantillonnage (frames par seconde)
lowcut = 0.85  # Fréquence de coupure basse (Hz)
highcut = 2.3  # Fréquence de coupure haute (Hz)
order = 4  # Ordre du filtre
frame_idx = []
max_frame_HR = 500
max_frame_HRV = 510
max_frame_respiration = 520
max_frame_SPO2 = 530
max_frame_pressions = 540
max_frame_total = 600

app = FastAPI()
# Liste des origines autorisées
allowed_origins = ["http://localhost:8001"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
)
# Excution du thread methode 
# executor = ThreadPoolExecutor(max_workers=4)

# Initialisation du détecteur de visage
face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')

# fonction reset du signaux
def reset_signals_if_exceeds(frame_idx, signals, metrics):
    # Réinitialiser tous les signaux et métriques
    signals["rppg_signal"].clear()
    signals["ppg_red_signal"].clear()
    signals["ppg_infra_signal"].clear()
    signals["heart_rates"].clear()
    signals["spo2_rates"].clear()
    signals["hrv_rates"].clear()
    signals["respiration_rates"].clear()
    signals["systolic_rates"].clear()
    signals["diastolic_rates"].clear()
    metrics["avg_bpm"] = 0
    metrics["avg_spo2"] = 0
    metrics["avg_hrv"] = 0
    metrics["avg_respiration"] = 0
    metrics["avg_systolic"] = 0
    metrics["avg_diastolic"] = 0
    frame_idx.clear()
    

UPLOAD_FOLDER = 'uploads/'
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)
    
# Variables pour stocker les signaux RGB et les indices de cadre
signals = {"rppg_signal": []  ,  "heart_rates": [], "spo2_rates": [],"hrv_rates": [], "respiration_rates": [], "systolic_rates": [],
    "diastolic_rates": [], "ppg_red_signal": [], "ppg_infra_signal": []}

# Variables moyennes et actuelles pour les signaux physiologiques
metrics = {"avg_bpm": 0, "bpm": 0, "avg_hrv": 0, "hrv": 0,
    "avg_spo2": 0, "spo2": 0, "avg_respiration": 0, "respiration": 0,
    "avg_diastolic": 0, "diastolic": 0, "avg_systolic": 0, "systolic": 0}

# Variables pour stocker les scores calculee par les metrics du signaux vitaux
scores = {"activity_score" : 0 ,"sleep_score" :0 ,  "equilibrium_score" :0 ,
        "metabolism_score" :0 ,"health_score" :0 ,"relaxation_score" :0 }


@app.post("/upload_video")
async def upload_video(age: int = Form(...), weight: int = Form(...), height: int = Form(...), video: UploadFile = File(...)):

    # Autres variables
    stress_level_label = ''
    global signals , metrics , scores , frame_idx 
    
    # Sauvegarder la vidéo temporairement
    video_path = os.path.join(UPLOAD_FOLDER, video.filename)
    print('le path est :', video_path)
    # Appeler la fonction pour réinitialiser les signaux si nécessaire
    reset_signals_if_exceeds(frame_idx, signals, metrics)
    
    with open(video_path, "wb") as buffer:
        buffer.write(await video.read())
    cap = cv2.VideoCapture(video_path)
    
    # Vérifier si la vidéo est bien chargée
    if not cap.isOpened():
        print("Erreur lors du chargement de la vidéo.")
        exit()
        
    # Boucle pour traiter chaque frame de la vidéo
    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break
        # Ajouter l'index de la frame à la liste
        frame_idx.append(len(frame_idx) + 1)
        
        # if len(frame_idx) % 3 == 0: 
        # Détecter le visage
        face_roi, _, _, w, h = detect_face(frame)
        if face_roi is not None:
            is_confident, _ = filter_by_confidence(w, h, frame.shape, threshold=8)
            if is_confident:
                # Convertir l'image BGR en RGB
                roi_rgb = cv2.cvtColor(face_roi, cv2.COLOR_BGR2RGB)

                # Calculer la moyenne des canaux R, G et B
                avg_color = np.mean(roi_rgb, axis=(0, 1))
                signals["rppg_signal"].append(avg_color[1])  # Utilisation du canal vert (G)

                # Combinaison des canaux RGB pour estimer le signal infrarouge
                avg_red = np.mean(roi_rgb[:, :, 0])  # utilisation du canal rouge (R)
                avg_infra = 0.3 * avg_red + 0.59 * avg_color[1] + 0.11 * np.mean(roi_rgb[:, :, 2])

                # Ajouter les signaux nécessaires dans la mesure du SPO2
                signals["ppg_red_signal"].append(avg_red)
                signals["ppg_infra_signal"].append(avg_infra)

                if len(signals["rppg_signal"]) > 33:
                    # Calculer la fréquence cardiaque (HR)
                    filtered_signal = bandpass_filter(signals["rppg_signal"], lowcut, highcut, fs, order)
                    bpm, peak_intervals, peaks = calculate_heart_rate(filtered_signal, fs)
                    signals["heart_rates"].append(bpm)
                    metrics["avg_bpm"] = round(np.mean(signals["heart_rates"]), 2) if len(signals["heart_rates"]) == max_frame_total else metrics["avg_bpm"]
                    
                    # Calculer la SPO2
                    if verify_signal_strength(signals["ppg_red_signal"]) and verify_signal_strength(signals["ppg_infra_signal"]):
                        spo2 = calculate_spo2(signals["ppg_red_signal"], signals["ppg_infra_signal"], fs)
                        signals["spo2_rates"].append(spo2)
                        metrics["avg_spo2"] = round(np.mean(signals["spo2_rates"]), 2) if len(signals["spo2_rates"]) == max_frame_total else metrics["avg_spo2"]
                
                    # Calculer la variabilité de la fréquence cardiaque (HRV)
                    if len(peaks) > 1:
                        _, hrv, _ = calculate_hrv(peaks)
                        signals["hrv_rates"].append(hrv)
                        metrics["avg_hrv"] = round(np.mean(signals["hrv_rates"]), 2) if len(signals["hrv_rates"]) == max_frame_total else metrics["avg_hrv"]
                        
                    # Déterminer le niveau de stress
                    stress_level_label = calculate_stress_level(peak_intervals)
                    
                    # Calculer la fréquence respiratoire
                    respiration = calculate_respiration_rate(filtered_signal, fs)
                    signals["respiration_rates"].append(respiration)
                    metrics["avg_respiration"] = round(np.mean(signals["respiration_rates"]), 2) if len(signals["respiration_rates"]) == max_frame_total else metrics["avg_respiration"]
                    
                    # Calculer la pression artérielle
                    systolic, diastolic = calculate_blood_pressure(peak_intervals)
                    if systolic and diastolic:
                        signals["systolic_rates"].append(systolic)
                        signals["diastolic_rates"].append(diastolic)
                        metrics["avg_systolic"] = round(np.mean(signals["systolic_rates"]), 2) if len(signals["systolic_rates"]) == max_frame_total else metrics["avg_systolic"]
                        metrics["avg_diastolic"] = round(np.mean(signals["diastolic_rates"]), 2) if len(signals["diastolic_rates"]) == max_frame_total else metrics["avg_diastolic"]
                if len(signals["rppg_signal"]) > max_frame_total:
                    scores["activity_score"] = calculate_activity(metrics["avg_bpm"], age)
                    scores["sleep_score"] = calculate_sleep(metrics["avg_hrv"], metrics["avg_respiration"])
                    scores["equilibrium_score"] = calculate_equilibrium(metrics["avg_hrv"], metrics["avg_systolic"], metrics["avg_diastolic"])
                    scores["metabolism_score"] = calculate_metabolism(weight, height, age)
                    scores["health_score"] = calculate_health(metrics["avg_spo2"], metrics["avg_bpm"], metrics["avg_systolic"])
                    scores["relaxation_score"] = calculate_relaxation(metrics["avg_hrv"], metrics["avg_respiration"]) 
            print('les mesures sont :', len(frame_idx) ,  metrics["avg_bpm"], metrics["avg_hrv"], metrics["avg_spo2"], metrics["avg_respiration"], metrics["avg_diastolic"], metrics["avg_systolic"], stress_level_label )
    cap.release()
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