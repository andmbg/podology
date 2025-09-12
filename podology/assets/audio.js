function setupAudioClickHandler() {
    const audio = document.getElementById("audio-player");
    if (!audio) return false;

    document.addEventListener("click", function (event) {
        const seg = event.target.closest(".transcript-segment");
        if (seg && seg.dataset.start) {
            audio.currentTime = parseFloat(seg.dataset.start);
            audio.play();
        }
    });
    console.log("Audio click handler attached");
    return true;
}

if (!setupAudioClickHandler()) {
    // If audio not found, observe DOM changes
    const observer = new MutationObserver(function () {
        if (setupAudioClickHandler()) {
            observer.disconnect();
        }
    });
    observer.observe(document.body, { childList: true, subtree: true });
}

function highlightActiveSegment() {
    const audio = document.getElementById("audio-player");
    if (!audio) return false;

    const segments = document.querySelectorAll(".transcript-segment");
    if (!segments.length) return false;

    audio.addEventListener("timeupdate", function () {
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
    });

    return true;
}

// Attach when audio and segments are present
if (!highlightActiveSegment()) {
    const observer = new MutationObserver(function () {
        if (highlightActiveSegment()) {
            observer.disconnect();
        }
    });
    observer.observe(document.body, { childList: true, subtree: true });
}
