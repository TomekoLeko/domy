/**
 * Prints "Hello World!" to the console
 */


//  get methods
function fetchData(url, formFields = {}) {
    const formData = new FormData();
    for (const key in formFields) {
        formData.append(key, formFields[key]);
    }

    return fetch(url, {
        method: 'POST',
        headers: {
            'X-Requested-With': 'XMLHttpRequest'
        },
        body: formData
    })
    .then(response => {
        if (!response.ok) {
            throw new Error('Network response was not ok: ' + response.statusText);
        }
        return response.json();
    })
    .catch(error => {
        console.error('Request failed:', error);
        return null;
    });
}

