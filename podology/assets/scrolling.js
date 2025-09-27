window.dash_clientside = Object.assign({}, window.dash_clientside, {
    ticker: {
        setup_scroll_listener: function (n_intervals) {
            console.log("setup_scroll_listener called with:", n_intervals);

            function setupScrollListener() {
                const transcriptEl = document.getElementById('transcript');
                if (transcriptEl) {
                    console.log("Found transcript element, setting up scroll listener");
                    let throttleTimer = null;

                    transcriptEl.addEventListener('scroll', function () {
                        if (throttleTimer) clearTimeout(throttleTimer);
                        throttleTimer = setTimeout(function () {
                            const scrollTop = transcriptEl.scrollTop;
                            const scrollHeight = transcriptEl.scrollHeight - transcriptEl.clientHeight;
                            const scrollPercent = scrollHeight > 0 ? scrollTop / scrollHeight : 0;

                            console.log("Scroll detected:", scrollPercent);

                            // Update the store
                            if (window.dash_clientside && window.dash_clientside.set_props) {
                                window.dash_clientside.set_props('scroll-position-store', { data: scrollPercent });
                            }
                        }, 16); // ~60fps
                    });
                } else {
                    console.log("Transcript element not found, will retry...");
                    // Retry after a short delay
                    setTimeout(setupScrollListener, 100);
                }
            }

            // Wait for DOM to be ready
            if (document.readyState === 'loading') {
                document.addEventListener('DOMContentLoaded', setupScrollListener);
            } else {
                setupScrollListener();
            }

            return window.dash_clientside.no_update;
        },

        // Function to parse duration string to seconds
        parseDurationToSeconds: function (durationString) {
            if (!durationString || durationString === "") {
                return 3600; // default 1 hour
            }

            // Remove any whitespace and split by ":"
            const parts = durationString.trim().split(":");
            let seconds = 0;

            try {
                if (parts.length === 1) {
                    // Just seconds: "45"
                    seconds = parseInt(parts[0]) || 0;
                } else if (parts.length === 2) {
                    // Minutes and seconds: "12:45"
                    const minutes = parseInt(parts[0]) || 0;
                    const secs = parseInt(parts[1]) || 0;
                    seconds = minutes * 60 + secs;
                } else if (parts.length === 3) {
                    // Hours, minutes, and seconds: "1:23:45"
                    const hours = parseInt(parts[0]) || 0;
                    const minutes = parseInt(parts[1]) || 0;
                    const secs = parseInt(parts[2]) || 0;
                    seconds = hours * 3600 + minutes * 60 + secs;
                } else {
                    console.warn("Unexpected duration format:", durationString);
                    return 3600; // default
                }

                return seconds > 0 ? seconds : 3600; // ensure positive, default if 0

            } catch (error) {
                console.error("Error parsing duration:", durationString, error);
                return 3600; // default
            }
        },

        update_ticker_from_scroll: function (scroll_percent, episode_duration, ticker_data) {
            console.log("update_ticker_from_scroll called with:", {
                scroll_percent,
                episode_duration,
                ticker_data: ticker_data ? "data present" : "no data"
            });

            // Check if we have valid ticker data
            if (!ticker_data || ticker_data === "" || !ticker_data.lanes || ticker_data.lanes.length === 0) {
                console.log("No valid ticker data, returning no_update");
                return window.dash_clientside.no_update;
            }

            // Get the height of the transcript element
            const transcriptEl = document.getElementById('transcript');
            const plotHeight = transcriptEl ? transcriptEl.clientHeight : 600; // fallback to 600px

            // Parse duration using our helper function
            const duration = window.dash_clientside.ticker.parseDurationToSeconds(episode_duration);
            console.log("Parsed duration:", duration, "seconds from:", episode_duration);

            // Calculate time code from scroll position
            const time_code = scroll_percent * duration;

            const window_width = 120;
            const window_start = time_code - window_width / 2;
            const window_end = time_code + window_width / 2;

            const annotations = [];

            ticker_data.lanes.forEach((lane, lane_idx) => {
                const y_pos = lane_idx === 0 ? 0 :
                    lane_idx % 2 === 1 ? Math.ceil(lane_idx / 2) :
                        -Math.floor(lane_idx / 2);

                lane.forEach(appearance => {
                    const start = appearance.start;
                    const end = appearance.end;
                    const term = appearance.term;

                    if (end >= window_start && start <= window_end) {
                        const rel_start = Math.max(0, start - window_start);
                        const rel_end = Math.min(window_width, end - window_start);
                        const text_x = (rel_start + rel_end) / 2;

                        // Calculate opacity based on distance from window center
                        const window_center = window_width / 2;
                        const distance_from_center = Math.abs(text_x - window_center);
                        const max_distance = window_width / 2;

                        const normalized_distance = distance_from_center / max_distance; // 0 to 1
                        const curve_factor = Math.pow(normalized_distance, 2);

                        const opacity = 1.0 - (curve_factor * 1.0);

                        // Color calculation: cornflower blue at center, black at edges
                        let color;
                        if (normalized_distance >= 0.5) {
                            // Beyond 0.5 relative distance: always black
                            color = "rgb(0, 0, 0)";
                        } else {
                            // 0 to 0.5 relative distance: interpolate between cornflower blue and black
                            // Use square function for smooth transition
                            const color_factor = Math.pow(normalized_distance / 0.5, 2); // 0 to 1 (squared)

                            // Cornflower blue RGB: (100, 149, 237)
                            // Black RGB: (0, 0, 0)
                            // Interpolate between them
                            const r = Math.round(100 * (1 - color_factor));
                            const g = Math.round(149 * (1 - color_factor));
                            const b = Math.round(237 * (1 - color_factor));

                            color = `rgb(${r}, ${g}, ${b})`;
                        }

                        annotations.push({
                            x: text_x,
                            y: y_pos,
                            text: term,
                            showarrow: false,
                            font: { size: 40, color: color },
                            bgcolor: "rgba(0,0,0,0)",
                            borderwidth: 0,
                            opacity: opacity
                        });
                    }
                });
            });

            console.log("Returning figure with", annotations.length, "annotations");

            return {
                data: [],
                layout: {
                    margin: { l: 0, r: 0, t: 0, b: 0 },
                    plot_bgcolor: "rgba(0,0,0,0)",
                    paper_bgcolor: "rgba(0,0,0,0)",
                    xaxis: {
                        title: null,
                        range: [0, window_width],
                        showgrid: false,
                        showticklabels: false,
                        zeroline: false
                    },
                    yaxis: {
                        title: null,
                        showticklabels: false,
                        range: [-(ticker_data.lanes.length * 0.5), ticker_data.lanes.length * 0.5],
                        showgrid: false,
                        zeroline: false
                    },
                    height: plotHeight,
                    showlegend: false,
                    annotations: annotations,
                    dragmode: false,
                    clickmode: "none"
                }
            };
        }
    },

    visible_span: {
        get_visible_span: function(transcript_children, selected_episode) {
            try {
                if (!transcript_children || !window.IntersectionObserver) {
                    return "No segments visible";
                }
                
                // Clean up existing observer
                if (window.transcriptObserver) {
                    window.transcriptObserver.disconnect();
                    window.transcriptObserver = null;
                }
                
                const transcript = document.getElementById('transcript');
                if (!transcript) {
                    return "Transcript element not found";
                }
                
                // Set up observer after a delay
                setTimeout(() => {
                    const segments = transcript.querySelectorAll('span[data-start]');
                    console.log(`Setting up observer for ${segments.length} segments`);
                    
                    if (segments.length === 0) {
                        return;
                    }
                    
                    let visibleSegments = new Set();
                    
                    window.transcriptObserver = new IntersectionObserver((entries) => {
                        try {
                            entries.forEach(entry => {
                                const segmentStart = entry.target.dataset.start;
                                const segmentEnd = entry.target.dataset.end;
                                
                                if (segmentStart && segmentEnd) {
                                    const segmentId = `${segmentStart}-${segmentEnd}`;
                                    
                                    if (entry.isIntersecting) {
                                        visibleSegments.add(segmentId);
                                    } else {
                                        visibleSegments.delete(segmentId);
                                    }
                                }
                            });
                            
                            // Update display
                            const segments = Array.from(visibleSegments).sort((a, b) => {
                                return parseFloat(a.split('-')[0]) - parseFloat(b.split('-')[0]);
                            });
                            
                            const visibleDiv = document.getElementById('visible-segments');
                            if (visibleDiv && segments.length > 0) {
                                const firstTime = parseFloat(segments[0].split('-')[0]).toFixed(1);
                                const lastTime = parseFloat(segments[segments.length - 1].split('-')[1]).toFixed(1);
                                visibleDiv.textContent = `Visible: ${firstTime}s → ${lastTime}s [${segments.length} segments]`;
                            } else if (visibleDiv) {
                                visibleDiv.textContent = "No segments visible";
                            }
                        } catch (e) {
                            console.error("Error in intersection observer:", e);
                        }
                    }, {
                        root: transcript,
                        rootMargin: '-10px',
                        threshold: 0.1
                    });
                    
                    segments.forEach(segment => {
                        window.transcriptObserver.observe(segment);
                    });
                    
                }, 500);
                
                return "Setting up segment observer...";
                
            } catch (error) {
                console.error("Error in visible segments callback:", error);
                return "Error setting up observer";
            }
        }
    }
});