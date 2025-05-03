var dagcomponentfuncs = (window.dashAgGridComponentFunctions = window.dashAgGridComponentFunctions || {});

dagcomponentfuncs.CustomTooltip = function (props) {
    // Extract the value of the cell
    const cellValue = props.value || "";
    const titleValue = props.data?.title || "Untitled";

    const tooltipContent = `<b>${titleValue}</b><br>${cellValue}`;

    // Return the tooltip as a React element with rendered HTML
    return React.createElement("div", {
        className: "custom-tooltip",
        dangerouslySetInnerHTML: { __html: tooltipContent }, // Render HTML content
    });
};

var dagfuncs = (window.dashAgGridFunctions = window.dashAgGridFunctions || {});

dagfuncs.setPopupsParent = () => {
    return document.querySelector('body')
}
