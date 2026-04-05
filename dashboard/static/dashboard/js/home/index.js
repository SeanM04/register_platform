import { createHomeContext } from "./context.js?v=20260403-home-story04";
import { initialiseFacultyLoadSection } from "./faculty_load.js?v=20260403-home-story04";
import { initialiseFullscreenControls } from "./fullscreen.js?v=20260403-home-story04";
import { renderStoryBanner } from "./narratives.js?v=20260403-home-story04";
import { initialiseOutcomeSection } from "./outcomes.js?v=20260403-home-story04";
import { initialiseProgressSection } from "./progress.js?v=20260403-home-story04";
import { initialiseRiskDistributionSection } from "./risk_distribution.js?v=20260403-home-story04";

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

export const initialiseOverviewPage = () => {
    const context = createHomeContext();

    if (!context.elements.storyBanner) {
        return;
    }

    renderStoryBanner(
        context.elements.storyBanner,
        context.data.outcomeRows,
        context.data.riskDistributionRows,
        context.data.facultyLoadRows,
        context.data.progressRows,
    );

    const controllers = [
        initialiseOutcomeSection(context),
        initialiseRiskDistributionSection(context),
        initialiseFacultyLoadSection(context),
        initialiseProgressSection(context),
    ];

    const resizeCharts = () => {
        controllers.forEach((controller) => {
            controller.resize();
        });
    };

    initialiseChartResizeHandling(controllers, resizeCharts);
    initialiseFullscreenControls(context.elements.fullscreenButtons, resizeCharts);
};
