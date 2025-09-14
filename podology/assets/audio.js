let currentAudioListeners = [];

function setupAudioClickHandler() {
    const audio = document.getElementById("audio-player");
    if (!audio) return false;

    // Remove existing click listeners to avoid duplicates
    document.removeEventListener("click", handleTranscriptClick);
    
    // Add new click listener
    document.addEventListener("click", handleTranscriptClick);
    
    console.log("Audio click handler attached");
    return true;
}

function handleTranscriptClick(event) {
    const audio = document.getElementById("audio-player");
    if (!audio) return;
    
    const seg = event.target.closest(".transcript-segment");
    if (seg && seg.dataset.start) {
        audio.currentTime = parseFloat(seg.dataset.start);
        audio.play();
    }
}

function highlightActiveSegment() {
    const audio = document.getElementById("audio-player");
    if (!audio) return false;

    // Remove existing timeupdate listeners
    currentAudioListeners.forEach(listener => {
        audio.removeEventListener("timeupdate", listener);
    });
    currentAudioListeners = [];

    const segments = document.querySelectorAll(".transcript-segment");
    if (!segments.length) return false;

    // Create new timeupdate listener
    const timeUpdateListener = function () {
        const currentTime = audio.currentTime;
        segments.forEach(seg => {
            const start = parseFloat(seg.dataset.start);
            const end = parseFloat(seg.dataset.end);
            if (currentTime >= start && currentTime < end) {
                seg.classList.add("active-segment");
            } else {
                seg.classList.remove("active-segment");
            }
        });
    };

    // Add the new listener and store reference
    audio.addEventListener("timeupdate", timeUpdateListener);
    currentAudioListeners.push(timeUpdateListener);

    console.log("Audio highlight handler attached to", segments.length, "segments");
    return true;
}

function initAudioHandlers() {
    if (setupAudioClickHandler() && highlightActiveSegment()) {
        return true;
    }
    return false;
}

// Initial setup
if (!initAudioHandlers()) {
    // If audio not found, observe DOM changes
    const observer = new MutationObserver(function (mutations) {
        // Check if transcript content changed
        const transcriptChanged = mutations.some(mutation => 
            Array.from(mutation.addedNodes).some(node => 
                node.nodeType === 1 && (
                    node.id === "transcript" || 
                    node.querySelector && node.querySelector("#transcript")
                )
            )
        );
        
        if (transcriptChanged || initAudioHandlers()) {
            // Don't disconnect observer - we want to re-attach on every transcript change
            console.log("Re-attached audio handlers after DOM change");
        }
    });
    observer.observe(document.body, { 
        childList: true, 
        subtree: true 
    });
}

// Also re-attach when transcript div content changes specifically
const transcriptObserver = new MutationObserver(function(mutations) {
    const hasTranscriptChanges = mutations.some(mutation => 
        mutation.target.id === "transcript" || 
        (mutation.target.closest && mutation.target.closest("#transcript"))
    );
    
    if (hasTranscriptChanges) {
        // Small delay to ensure DOM is fully updated
        setTimeout(() => {
            initAudioHandlers();
            console.log("Re-attached audio handlers after transcript content change");
        }, 100);
    }
});

// Observe transcript div specifically
setTimeout(() => {
    const transcriptDiv = document.getElementById("transcript");
    if (transcriptDiv) {
        transcriptObserver.observe(transcriptDiv, {
            childList: true,
            subtree: true
        });
    }
}, 1000);
