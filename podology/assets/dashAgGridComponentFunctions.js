var dagcomponentfuncs = (window.dashAgGridComponentFunctions = window.dashAgGridComponentFunctions || {});

dagcomponentfuncs.CustomTooltip = function (props) {
    const cellValue = props.value || "";
    const titleValue = props.data?.title || "Untitled";
    const wordcloudUrl = props.data?.wordcloud_url;

    let tooltipContent = "<div style='display:flex;flex-direction:column;align-items:center;'>";
    if (wordcloudUrl) {
        tooltipContent += `
            <div style="background:white;border:0;padding:8px;margin-bottom:8px;">
                <img src="${wordcloudUrl}" style="max-width:100%;display:block;"/>
            </div>
        `;
    } else {
        tooltipContent += `<div style="height:0;margin-bottom:0;"></div>`;
    }
    tooltipContent += `
        <div style="background:#ffffee;border:1px solid #fff;padding:8px;box-shadow:0 2px 8px rgba(0,0,0,0.15);">
            <b>${titleValue}</b><br>${cellValue}
        </div>
    `;
    tooltipContent += "</div>";

    return React.createElement("div", {
        className: "custom-tooltip",
        dangerouslySetInnerHTML: { __html: tooltipContent },
    });
};
