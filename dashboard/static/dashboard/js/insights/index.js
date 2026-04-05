import { createInsightContext } from "./context.js?v=20260403-insights-story02";
import { initialiseDistributionSection } from "./distribution.js?v=20260403-insights-story02";
import { initialiseDriversSection } from "./drivers.js?v=20260403-insights-story02";
import { initialiseFacultyLoadSection } from "./faculty_load.js?v=20260403-insights-story02";
import { initialiseFacultyPressureSection } from "./faculty_pressure.js?v=20260403-insights-story02";
import { initialiseFullscreenControls } from "./fullscreen.js?v=20260403-insights-story02";
import { renderStoryBanner } from "./narratives.js?v=20260403-insights-story02";

const initialiseChartResizeHandling = (controllers, resizeCharts) => {
    const charts = controllers
        .map((controller) => controller.getChart())
        .filter(Boolean);

    if (!charts.length) {
        return;
    }

    window.addEventListener("resize", resizeCharts);

    if (!window.ResizeObserver) {
        return;
    }

    const observer = new ResizeObserver(() => {
        resizeCharts();
    });

    charts.forEach((chart) => {
        observer.observe(chart.getDom());
    });
};

export const initialiseInsightsPage = () => {
    const context = createInsightContext();
    const { data, elements } = context;

    renderStoryBanner(
        elements.storyBanner,
        data.distributionRows,
        data.facultyLoadRows,
        data.facultyPressureRows,
        data.driverRows,
    );

    const controllers = [
        initialiseDistributionSection(context),
        initialiseFacultyLoadSection(context),
        initialiseFacultyPressureSection(context),
        initialiseDriversSection(context),
    ];
    const resizeCharts = () => {
        controllers.forEach((controller) => {
            controller.resize();
        });
    };

    initialiseChartResizeHandling(controllers, resizeCharts);
    initialiseFullscreenControls(elements.fullscreenButtons, resizeCharts);
};
