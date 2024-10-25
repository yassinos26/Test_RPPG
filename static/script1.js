// Fonction pour revenir à la page précédente
function goBack() {
    window.location.href = '/';
}

// Déclarez les couleurs ici pour les utiliser dans JavaScript
const statusColors = {
    bad: '#fc0202',       // Red
    moderate: '#fccf02',  // Orange
    good: '#02fc11',      // Green
    excellent: '#33fff3', // Blue Sky
    perfect: '#3633ff'    // Blue
};

// Récupérer les données du Local Storage
const age = localStorage.getItem('age');
const weight = localStorage.getItem('weight');
const height = localStorage.getItem('height');
const info = {
    age: age,
    weight: weight,
    height: height
};
//console.log('les informations sont',info);
const information = JSON.stringify(info);

document.getElementById('backButton').addEventListener('click', function() {
    window.location.href = '/';
});

const socket = io('http://localhost:5000/')
socket.on('connect', function() {
    document.getElementById("status").innerText = "Status: Server Connected Successfully!";
    socket.emit('info', information);  // Envoyer l'objet info  
    socket.emit('reset', 'reset'); // Envoyer l'objet
});

socket.on('connect_error', function() {
    document.getElementById("status").innerText = "Status: Impossible To Server Connect!";
});

const video = document.querySelector("#videoElement");
const canvasInput = document.querySelector("#canvasInput");
const canvasOutput = document.querySelector("#canvasOutput");
const contextInput = canvasInput.getContext("2d");
const contextOutput = canvasOutput.getContext("2d");
const resultDiv = document.getElementById("result");  // Div to display the backend result
const scoreDiv = document.getElementById("scores-container");  // Div to display the backend scores

// Définir des objets globaux pour metrics et scores
let metrics = {
    bpm: 0,
    hrv: 0,
    spo2: 0,
    respiration: 0,
    diastolic: 0,
    systolic: 0
};

let scores = {
    activity_score: 0,
    sleep_score: 0,
    equilibrium_score: 0,
    metabolism_score: 0,
    health_score: 0,
    relaxation_score: 0
};

// Initialisation du graphique radar
const radarChartCtx = document.getElementById('radarChart').getContext('2d');
const radarChart = new Chart(radarChartCtx, {
    type: 'radar',
    data: {
        labels: ['Activity', 'Sleep', 'Equilibrium', 'Metabolism', 'Health', 'Relaxation'],
        datasets: [{
            label: 'Scores Graphics',
            data: [0, 0, 0, 0, 0, 0], // Données initiales vides
            backgroundColor: 'rgba(54, 162, 235, 0.2)',
            borderColor: 'rgba(54, 162, 235, 1)',
            borderWidth: 4
        }]
    },
    options: {
        responsive: true,
        scale: {
            ticks: {
                beginAtZero: true,
                max: 5, // Max de l'échelle des scores est de 0 à 5
                stepSize: 1,
                suggestedMin: 0, // Pour que l'échelle commence à 0
            }
        }
    }
});

// Fonction pour mettre à jour le radar chart avec de nouveaux scores
function updateRadarChart(scores) {
    radarChart.data.datasets[0].data = [
        scores.activity_score,
        scores.sleep_score,
        scores.equilibrium_score,
        scores.metabolism_score,
        scores.health_score,
        scores.relaxation_score
    ];
    radarChart.update();
}

// Fonction pour réinitialiser les valeurs de metrics
function clearMetrics(metrics) {
    metrics.bpm = 0;
    metrics.hrv = 0;
    metrics.spo2 = 0;
    metrics.respiration = 0;
    metrics.diastolic = 0;
    metrics.systolic = 0
}

// Fonction pour réinitialiser les valeurs de scores
function clearScores(scores) {
    scores.activity_score = 0;
    scores.sleep_score = 0;
    scores.equilibrium_score = 0;
    scores.metabolism_score = 0;
    scores.health_score = 0;
    scores.relaxation_score = 0
}

// Access the user's webcam
navigator.mediaDevices.getUserMedia({ video: true })
    .then(function(stream) {
        video.srcObject = stream;
        video.play();
        startCapturing();
    })
    .catch(function(err) {
        console.log("An error occurred: " + err);
    });

let intervalID; // Variable pour stocker l'ID de l'intervalle
const FPS = 7; // Set desired FPS
function startCapturing() {
    intervalID = setInterval(() => {
        contextInput.drawImage(video, 0, 0, canvasInput.width, canvasInput.height);

        var type = "image/jpeg";
        data = canvasInput.toDataURL(type, 0.75);
        data = data.replace('data:' + type + ';base64,', '');
        socket.emit('image', data);
    }, 1000 / FPS);
}

function stopCapturing() { // Function to clear the interval
    clearInterval(intervalID); // Clear the stored interval
}

//Excution du 1ere socket du traitement frames
socket.on('image_back', function(response) {
    
    const imageData = response;

    const img = new Image();
    img.src = imageData;

    img.onload = () => {
        contextOutput.clearRect(0, 0, canvasOutput.width, canvasOutput.height);
        contextOutput.drawImage(img, 0, 0, canvasOutput.width, canvasOutput.height);
    }
});

//Excution du 2eme socket du calcul metrics
socket.on('metrics_back', function(response) {
    const result = response;
    
    // Update the HTML with the received values
    document.getElementById('heart-rate-value').innerText = result.metrics.bpm;
    document.getElementById('hrv-value').innerText = result.metrics.hrv;
    document.getElementById('blood-pressure-value').innerText = `${result.metrics.systolic}/${result.metrics.diastolic}`;
    document.getElementById('spo2-value').innerText = result.metrics.spo2;
    document.getElementById('respiration-value').innerText = result.metrics.respiration;
    document.getElementById('stress-value').innerText = result.metrics.stress_level;

    // Mettre à jour l'objet metrics global
    metrics = result.metrics;

    // Effacer les valeurs des metrics et scores
    clearMetrics(metrics);
}); 
    
//Excution du 3eme socket du calcul scores
socket.on('scores_back', function(response) {
    const score = response;

    // Mettre à jour le graphique radar avec les nouvelles données
    updateRadarChart(score.scores);

    // Update each score value
    document.getElementById('activity-score').innerText = score.scores.activity_score;
    document.getElementById('sleep-score').innerText = score.scores.sleep_score;
    document.getElementById('equilibrium-score').innerText = score.scores.equilibrium_score;
    document.getElementById('metabolism-score').innerText = score.scores.metabolism_score;
    document.getElementById('health-score').innerText = score.scores.health_score;
    document.getElementById('relaxation-score').innerText = score.scores.relaxation_score;

    // Mettre à jour l'objet scores global
    scores = score.scores;
    
    // Fonction qui détermine le statut et retourne la couleur et le texte du statut
    function getScoreStatus(scoreValue) {
        if (scoreValue < 1) {
            return { status: 'Bad', color: statusColors.bad };
        } else if (scoreValue >= 1 && scoreValue < 2) {
            return { status: 'Moderate', color: statusColors.moderate };
        } else if (scoreValue >= 2 && scoreValue < 3) {
            return { status: 'Good', color: statusColors.good };
        } else if (scoreValue >= 3 && scoreValue < 4) {
            return { status: 'Excellent', color: statusColors.excellent };
        } else {
            return { status: 'Perfect', color: statusColors.perfect };
        }
    }
    
    // Mise à jour du statut et de la couleur pour chaque score
    const activityStatus = getScoreStatus(score.scores.activity_score);
    document.getElementById('activity_status').innerText = activityStatus.status;
    document.getElementById('activity_status').style.color = activityStatus.color;
    
    const sleepStatus = getScoreStatus(score.scores.sleep_score);
    document.getElementById('sleep_status').innerText = sleepStatus.status;
    document.getElementById('sleep_status').style.color = sleepStatus.color;

    const equilibriumStatus = getScoreStatus(score.scores.equilibrium_score);
    document.getElementById('equilibrium_status').innerText = equilibriumStatus.status;
    document.getElementById('equilibrium_status').style.color = equilibriumStatus.color;
    
    const metabolismStatus = getScoreStatus(score.scores.metabolism_score);
    document.getElementById('metabolism_status').innerText = metabolismStatus.status;
    document.getElementById('metabolism_status').style.color = metabolismStatus.color;
    
    const healthStatus = getScoreStatus(score.scores.health_score);
    document.getElementById('health_status').innerText = healthStatus.status;
    document.getElementById('health_status').style.color = healthStatus.color;
    
    const relaxationStatus = getScoreStatus(score.scores.relaxation_score);
    document.getElementById('relaxation_status').innerText = relaxationStatus.status;
    document.getElementById('relaxation_status').style.color = relaxationStatus.color;

    clearScores(scores);
});  

// Fonction pour masquer les canvases et la vidéo
function hideCanvasAndVideo() {
    document.getElementById('canvasInput').style.display = 'none';
    document.getElementById('canvasOutput').style.display = 'none';
    document.getElementById('videoElement').style.display = 'none';
}

//Excution du 4eme socket du fermeture du camera , video et canvas
socket.on('close_back', function(response) { 
    const finished = response;
    if (finished === 'True') {
        hideCanvasAndVideo(); // Masquer les éléments vidéo et canvas
        stopCapturing(); // Arrêter la capture des images en appelant stopCapturing

        // Reset the video source for future initialization
        if (video.srcObject) {
            const tracks = video.srcObject.getTracks();
            tracks.forEach(track => track.stop());
            video.srcObject = null;  // Clear video source
        }
    }
    console.log('everything is cleared')
});