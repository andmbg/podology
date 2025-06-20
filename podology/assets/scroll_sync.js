window.dash_clientside = Object.assign({}, window.dash_clientside, {
    scrollSync: {
        syncVideoToScroll: function(video_id, transcript_id) {
            setTimeout(function () {
                const video = document.getElementById(video_id);
                const transcript = document.getElementById(transcript_id);
                if (!video || !transcript) return;

                let targetTime = 0;
                let lastScrollTop = -1;

                function updateTargetTimeFromScroll() {
                    const maxScroll = transcript.scrollHeight - transcript.clientHeight;
                    const scrollFraction = transcript.scrollTop / maxScroll;
                    return scrollFraction * video.duration;
                }

                function animate() {
                    if (!video || !video.duration) {
                        requestAnimationFrame(animate);
                        return;
                    }

                    const currentScrollTop = transcript.scrollTop;
                    // Only recalculate targetTime if scroll position has changed
                    if (currentScrollTop !== lastScrollTop) {
                        targetTime = updateTargetTimeFromScroll();
                        lastScrollTop = currentScrollTop;
                    }

                    const current = video.currentTime;
                    const diff = targetTime - current;

                    if (Math.abs(diff) > 0.05) {
                        video.currentTime = current + diff * 0.15; // Smooth transition
                    }

                    requestAnimationFrame(animate);
                }

                // Start polling loop
                requestAnimationFrame(animate);
            }, 1000);
            return window.dash_clientside.no_update;
        }
    }
});
