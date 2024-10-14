# Function to estimate each parameter based on physiological data
def calculate_activity(heart_rate, age):
    max_heart_rate = 220 - age  # Fréquence cardiaque maximale estimée
    met_value = (heart_rate / max_heart_rate) * 15  # Le MET peut aller de 1 à 15
    activity_score = met_value / 3  # Normalisation sur une échelle de 0 à 5
    return round(min(max(activity_score, 0), 5), 2)  # Limite entre 0 et 5

def calculate_sleep(hrv, respiration_rate):
    normalized_hrv = hrv / 100  # Normalisation de HRV pour une échelle cohérente
    normalized_respiration_rate = respiration_rate / 30  # Fréquence respiratoire max autour de 30 BPM
    # Score basé sur la somme pondérée de HRV et de la fréquence respiratoire
    sleep_score = (0.6 * normalized_hrv + 0.6 * normalized_respiration_rate) * 5
    return round(min(max(sleep_score, 0), 5), 2)  # Limite entre 0 et 5

def calculate_equilibrium(hrv, blood_pressure_sys, blood_pressure_dia):
    if blood_pressure_sys is not None and blood_pressure_dia is not None :
        difference = abs(blood_pressure_sys - blood_pressure_dia) + 1
        equilibrium_score = (hrv / difference) * 2
    return round(min(equilibrium_score, 5), 2)

def calculate_metabolism(weight, height, age):
    bmr = 10 * weight + 6.25 * height - 5 * age + 5  # For men
    metabolism_score = (bmr / 2000) * 5  # Normalize on a scale of 5
    return round(min(metabolism_score, 5), 2)

def calculate_health(spo2, heart_rate, blood_pressure_sys):
    # Vérification si heart_rate et blood_pressure_sys ne sont pas zéro
    if heart_rate == 0 or blood_pressure_sys == 0:
        return 0  # Vous pouvez choisir une autre valeur par défaut ou une gestion d'erreur
    # General health based on key vitals like oxygen saturation, heart rate, and blood pressure
    health_score = (spo2 / 100 + 60 / heart_rate + 120 / blood_pressure_sys) / 3 * 5
    return round(min(health_score, 5), 2)

def calculate_relaxation(hrv, respiration_rate):
    if respiration_rate >7 : 
        relaxation_score = (hrv / respiration_rate) * 3
    else:
        relaxation_score = 0  # Ou une autre valeur par défaut
    return round(min(relaxation_score, 5), 2)
