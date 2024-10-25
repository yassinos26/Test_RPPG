document.getElementById('nextButton').addEventListener('click', function() {
    const age = document.getElementById('age').value;
    const weight = document.getElementById('weight').value;
    const height = document.getElementById('height').value;

    // Vérification des champs
    if (!age || !weight || !height) {
        alert('Veuillez remplir tous les champs.');
        return window.location.href = '/';
    }
    if (age > 120 || weight > 160 || height > 230) {
        alert('Les valeurs sont incorrectes');
        return window.location.href = '/';
    }
    if (age == 0 || weight == 0  || height == 0) {
        alert('Les valeurs sont nulles. Entrez les valeurs correctes.');
        return window.location.href = '/';
    }

    // Enregistrement des données dans le Local Storage
    localStorage.setItem('age', age);
    localStorage.setItem('weight', weight);
    localStorage.setItem('height', height);

    // Redirection vers la deuxième page
    window.location.href = 'cam';
});
