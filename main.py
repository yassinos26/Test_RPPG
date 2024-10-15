import cv2, os, numpy as np 
from flask_cors import CORS
from flask import Flask, request, jsonify
from face import detect_face, filter_by_confidence
from metrics import (calculate_activity, calculate_sleep, calculate_equilibrium,
                    calculate_metabolism, calculate_health, calculate_relaxation)
from vitals import (bandpass_filter, calculate_heart_rate, calculate_hrv, calculate_stress_level, calculate_blood_pressure,
                    calculate_spo2, verify_signal_strength, calculate_respiration_rate)
# Paramètres de capture
fs = 30  # Fréquence d'échantillonnage (frames par seconde)
lowcut = 0.8  # Fréquence de coupure basse (Hz)
highcut = 2.5  # Fréquence de coupure haute (Hz)
order = 4  # Ordre du filtre
frame_idx = []
stress_level_label =''
# Limites des frames pour calculer différents signaux vitaux
max_frame_HR = 500
max_frame_HRV = 510
max_frame_respiration = 520
max_frame_SPO2 = 530
max_frame_pressions = 540
max_frame_total = 600  # Limite pour les frames totales
# Initialisation de l'application Flask

app = Flask(__name__)

# Liste des origines autorisées
allowed_origins = ["http://localhost:8001"]

# Appliquer CORS à l'application Flask avec les origines autorisées
CORS(app, resources={r"/*": {"origins": allowed_origins}})

# Dossier pour stocker les vidéos téléchargées
UPLOAD_FOLDER = 'uploads/'
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

# Initialisation du détecteur de visage en utilisant le modèle Haar Cascade
face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')

# Variables pour stocker les signaux RGB et RPPG 
signals = {"rppg_signal": [], "heart_rates": [], "spo2_rates": [], "hrv_rates": [], "respiration_rates": [], 
        "systolic_rates": [], "diastolic_rates": [], "ppg_red_signal": [], "ppg_infra_signal": []}

# Variables moyennes et actuelles pour les signaux physiologiques
metrics = {"avg_bpm": 0, "bpm": 0, "avg_hrv": 0, "hrv": 0,
        "avg_spo2": 0, "spo2": 0, "avg_respiration": 0, "respiration": 0,
        "avg_diastolic": 0, "diastolic": 0, "avg_systolic": 0, "systolic": 0}

# Variables pour stocker les scores calculés par les métriques des signaux vitaux
scores = {"activity_score": 0, "sleep_score": 0, "equilibrium_score": 0,
        "metabolism_score": 0, "health_score": 0, "relaxation_score": 0}

# Fonction pour réinitialiser les signaux et les métriques si le nombre de frames dépasse une limite
def reset_signals_if_exceeds(frame_idx, signals, metrics):
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

# Route pour télécharger et traiter la vidéo
@app.route("/upload_video", methods=["POST"])
def upload_video():
    age = int(request.form["age"])
    weight = int(request.form["weight"])
    height = int(request.form["height"])
    video = request.files["video"]
    global signals, metrics, scores, frame_idx , stress_level_label 
    
    # Sauvegarder la vidéo temporairement
    video_path = os.path.join(UPLOAD_FOLDER, video.filename)
    print('le path est :', video_path)
    
    reset_signals_if_exceeds(frame_idx, signals, metrics)
    
    video.save(video_path)  # Enregistrer la vidéo sur le serveur
    cap = cv2.VideoCapture(video_path)  # Charger la vidéo

    # Vérifier si la vidéo a été correctement chargée
    if not cap.isOpened():
        return jsonify({"error": "Erreur lors du chargement de la vidéo."}), 400
        
    # Boucle pour traiter chaque frame de la vidéo
    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break  # Sortir de la boucle si la vidéo est terminée
        frame_idx.append(len(frame_idx) + 1)  # Ajouter l'index de la frame

        # Détecter le visage
        face_roi, _, _, w, h = detect_face(frame)
        if face_roi is not None:
            is_confident, _ = filter_by_confidence(w, h, frame.shape, threshold=8)
            if is_confident:
                roi_rgb = cv2.cvtColor(face_roi, cv2.COLOR_BGR2RGB)
                avg_color = np.mean(roi_rgb, axis=(0, 1))
                signals["rppg_signal"].append(avg_color[1])

                avg_red = np.mean(roi_rgb[:, :, 0])
                avg_infra = 0.3 * avg_red + 0.59 * avg_color[1] + 0.11 * np.mean(roi_rgb[:, :, 2])
                signals["ppg_red_signal"].append(avg_red)
                signals["ppg_infra_signal"].append(avg_infra)

                if len(signals["rppg_signal"]) > 33:
                    filtered_signal = bandpass_filter(signals["rppg_signal"], lowcut, highcut, fs, order)
                    bpm, peak_intervals, peaks = calculate_heart_rate(filtered_signal, fs)
                    signals["heart_rates"].append(bpm)
                    metrics["avg_bpm"] = round(np.mean(signals["heart_rates"]), 2)

                    if verify_signal_strength(signals["ppg_red_signal"]) and verify_signal_strength(signals["ppg_infra_signal"]):
                        spo2 = calculate_spo2(signals["ppg_red_signal"], signals["ppg_infra_signal"], fs)
                        signals["spo2_rates"].append(spo2)
                        metrics["avg_spo2"] = round(np.mean(signals["spo2_rates"]), 2)

                    if len(peaks) > 1:
                        _, hrv, _ = calculate_hrv(peaks)
                        signals["hrv_rates"].append(hrv)
                        metrics["avg_hrv"] = round(np.mean(signals["hrv_rates"]), 2)

                    stress_level_label = calculate_stress_level(peak_intervals)

                    respiration = calculate_respiration_rate(filtered_signal, fs)
                    signals["respiration_rates"].append(respiration)
                    metrics["avg_respiration"] = round(np.mean(signals["respiration_rates"]), 2)

                    systolic, diastolic = calculate_blood_pressure(peak_intervals)
                    if systolic and diastolic:
                        signals["systolic_rates"].append(systolic)
                        signals["diastolic_rates"].append(diastolic)
                        metrics["avg_systolic"] = round(np.mean(signals["systolic_rates"]), 2)
                        metrics["avg_diastolic"] = round(np.mean(signals["diastolic_rates"]), 2)
            print('les mesures sont :', len(frame_idx), metrics["avg_bpm"], metrics["avg_hrv"], metrics["avg_spo2"], 
                metrics["avg_respiration"], metrics["avg_diastolic"], metrics["avg_systolic"], stress_level_label)
    
    cap.release()
    os.remove(video_path)

    if len(signals["rppg_signal"]) > max_frame_total:
        scores["activity_score"] = calculate_activity(metrics["avg_bpm"], age)
        scores["sleep_score"] = calculate_sleep(metrics["avg_hrv"], metrics["avg_respiration"])
        scores["equilibrium_score"] = calculate_equilibrium(metrics["avg_hrv"], metrics["avg_systolic"], metrics["avg_diastolic"])
        scores["metabolism_score"] = calculate_metabolism(weight, height, age)
        scores["health_score"] = calculate_health(metrics["avg_spo2"], metrics["avg_bpm"], metrics["avg_systolic"])
        scores["relaxation_score"] = calculate_relaxation(metrics["avg_hrv"], metrics["avg_respiration"])

    return jsonify({
        "message": "Vidéo et données reçues avec succès",
        "age": age,
        "weight": weight,
        "height": height,
        "evaluation_HR": metrics["avg_bpm"],
        "evaluation_HRV": metrics["avg_hrv"],
        "evaluation_Spo2": metrics["avg_spo2"],
        "evaluation_respiration": metrics["avg_respiration"],
        "evaluation_diastolic": metrics["avg_diastolic"],
        "evaluation_systolic": metrics["avg_systolic"],
        "activity_score": scores["activity_score"],
        "sleep_score": scores["sleep_score"],
        "equilibrium_score": scores["equilibrium_score"],
        "metabolism_score": scores["metabolism_score"],
        "health_score": scores["health_score"],
        "relaxation_score": scores["relaxation_score"],
        "stress_level": stress_level_label
    })
if __name__ == "__main__":
    app.run(debug=True, port=5000)