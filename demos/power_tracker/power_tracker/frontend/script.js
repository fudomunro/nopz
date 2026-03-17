document.addEventListener('DOMContentLoaded', () => {
    const API_BASE_URL = 'http://localhost:8000';
    const peopleList = document.getElementById('people-list');
    const activityFeed = document.getElementById('activity-feed');
    const connectionStatus = document.getElementById('connection-status');
    const statusText = connectionStatus.querySelector('p');

    let eventSource;

    /**
     * Updates the connection status indicator in the UI.
     * @param {string} status - The connection status ('connected', 'connecting', 'disconnected').
     * @param {string} message - The text to display.
     */
    const updateConnectionStatus = (status, message) => {
        connectionStatus.className = `status-${status}`;
        statusText.textContent = message;
    };

    /**
     * Fetches the list of the 10 most powerful people and populates the UI.
     */
    const fetchPeople = async () => {
        try {
            const response = await fetch(`${API_BASE_URL}/people`);
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            const people = await response.json();
            peopleList.innerHTML = people.map(person => `
                <div class="person-card">
                    <span class="rank">#${person.power_rank}</span>
                    <div class="info">
                        <h3>${person.name}</h3>
                        <p>${person.title}, ${person.country_or_organization}</p>
                    </div>
                </div>
            `).join('');
        } catch (error) {
            console.error('Failed to fetch people:', error);
            peopleList.innerHTML = '<p style="color: red;">Could not load people data.</p>';
        }
    };

    /**
     * Adds a new activity to the top of the activity feed.
     * @param {object} activity - The activity object to add.
     */
    const addActivityToFeed = (activity) => {
        const activityItem = document.createElement('div');
        activityItem.className = 'activity-item';

        const timestamp = new Date(activity.timestamp).toLocaleTimeString();

        activityItem.innerHTML = `
            <p class="description">${activity.person_name} ${activity.description.toLowerCase()}.</p>
            <p class="meta">
                <span>${activity.location}</span> &bull;
                <span>${timestamp}</span>
            </p>
        `;

        activityFeed.insertBefore(activityItem, activityFeed.firstChild);

        // Limit the number of items in the feed to prevent performance issues
        while (activityFeed.children.length > 50) {
            activityFeed.removeChild(activityFeed.lastChild);
        }
    };

    /**
     * Initializes the connection to the Server-Sent Events (SSE) stream.
     */
    const connectToStream = () => {
        if (eventSource) {
            eventSource.close();
        }

        eventSource = new EventSource(`${API_BASE_URL}/activities/stream`);
        updateConnectionStatus('connecting', 'Connecting...');

        eventSource.onopen = () => {
            updateConnectionStatus('connected', 'Live');
            console.log('SSE connection established.');
        };

        eventSource.addEventListener('new_activity', (event) => {
            try {
                const activity = JSON.parse(event.data);
                addActivityToFeed(activity);
            } catch (error) {
                console.error('Failed to parse activity data:', error);
            }
        });

        eventSource.onerror = () => {
            console.error('SSE connection error. Attempting to reconnect...');
            updateConnectionStatus('disconnected', 'Reconnecting...');
            eventSource.close();
            // The browser will automatically try to reconnect every few seconds.
            // We can implement a more sophisticated backoff strategy here if needed.
            setTimeout(connectToStream, 5000); // Manually retry after 5 seconds
        };
    };

    // Initial load
    fetchPeople();
    connectToStream();
});
