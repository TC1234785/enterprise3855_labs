/* UPDATE THESE VALUES TO MATCH YOUR SETUP */

const PROCESSING_STATS_API_URL = "http://localhost:8100/stats"
const ANALYZER_API_URL = {
    stats: "http://localhost:8110/stats",
    passenger_count: "http://localhost:8110/na_train/passenger_count",
    incoming_train: "http://localhost:8110/na_train/incoming_train"
}
const HEALTH_API_URL = "http://localhost:8120/health"

// This function fetches and updates the general statistics
const makeReq = (url, cb) => {
    fetch(url)
        .then(res => {
            if (!res.ok) {
                throw new Error(`HTTP error! status: ${res.status}`);
            }
            return res.json();
        })
        .then((result) => {
            console.log("Received data: ", result)
            cb(result);
        }).catch((error) => {
            console.error(`Error fetching ${url}:`, error);
            updateErrorMessages(`${url}: ${error.message}`)
        })
}

const makeReqQuery = (url, query, cb) => {
    fetch(url + '?' + new URLSearchParams(query).toString())
        .then(res => res.json())
        .then((result) => {
            console.log("Received data: ", result)
            cb(result);
        }).catch((error) => {
            updateErrorMessages(error.message)
        })
}

const updateCodeDiv = (result, elemId) => document.getElementById(elemId).innerText = JSON.stringify(result)

const getLocaleDateStr = () => (new Date()).toLocaleString()

let max_passenger = 0
let max_train = 0

const getStats = () => {
    document.getElementById("last-updated-value").innerText = getLocaleDateStr()
    
    makeReq(HEALTH_API_URL, (result) => {
        const healthDisplay = `Receiver: ${result.receiver}\nStorage: ${result.storage}\nProcessing: ${result.processing}\nAnalyzer: ${result.analyzer}\nLast Updated: ${result.last_update}`
        document.getElementById("health-stats").innerText = healthDisplay
    })
    
    makeReq(PROCESSING_STATS_API_URL, (result) => updateCodeDiv(result, "processing-stats"))
    makeReq(ANALYZER_API_URL.stats, (result) => {
        max_passenger = result.num_passenger_readings || 0;
        max_train = result.num_wait_time_readings || 0;
        updateCodeDiv(result, "analyzer-stats")
    })
    
    if (max_passenger > 0) {
        makeReqQuery(ANALYZER_API_URL.passenger_count, { index: Math.floor(Math.random() * max_passenger) }, (result) => updateCodeDiv(result, "event-passenger"))
    }
    if (max_train > 0) {
        makeReqQuery(ANALYZER_API_URL.incoming_train, { index: Math.floor(Math.random() * max_train) }, (result) => updateCodeDiv(result, "event-train"))
    }
}

const updateErrorMessages = (message) => {
    const id = Date.now()
    console.log("Creation", id)
    msg = document.createElement("div")
    msg.id = `error-${id}`
    msg.innerHTML = `<p>Something happened at ${getLocaleDateStr()}!</p><code>${message}</code>`
    document.getElementById("messages").style.display = "block"
    document.getElementById("messages").prepend(msg)
    setTimeout(() => {
        const elem = document.getElementById(`error-${id}`)
        if (elem) { elem.remove() }
    }, 7000)
}

const setup = () => {
    getStats()
    setInterval(() => getStats(), 4000) // Update every 4 seconds
}

document.addEventListener('DOMContentLoaded', setup)