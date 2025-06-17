window.dash_clientside = Object.assign({}, window.dash_clientside, {
    scrollSync: {
        syncVideoToScroll: function(video_id, transcript_id) {
            // Wait for DOM to be ready
            setTimeout(function() {
                const video = document.getElementById(video_id);
                const transcript = document.getElementById(transcript_id);
                if (!video || !transcript) return;

                transcript.addEventListener('scroll', function() {
                    if (!video.duration) return;
                    const maxScroll = transcript.scrollHeight - transcript.clientHeight;
                    const scrollFraction = transcript.scrollTop / maxScroll;
                    video.currentTime = scrollFraction * video.duration;
                });
            }, 1000);
            return window.dash_clientside.no_update;
        }
    }
});
