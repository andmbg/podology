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
