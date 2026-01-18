document.getElementById('sendBtn').addEventListener('click', () => {
    const name = document.getElementById('nameInput').value;
    console.log("Hello World");

    fetch('/api/data', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({ name })
    })
    .then(response => {
        console.log("fetch status:", response.status);   // NEW
        return response.json();
    }
    )
    .then(data => {
        document.getElementById('response').textContent = data.message;
    })
    .catch(error => {
        console.error('Error:', error);
    });
});
