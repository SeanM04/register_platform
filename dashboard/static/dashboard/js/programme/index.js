import { createProgrammeContext } from "./context.js?v=20260404-programmes-story01";
import { initialiseDepartmentSection } from "./departments.js?v=20260404-programmes-story01";
import { initialiseFullscreenControls } from "./fullscreen.js?v=20260404-programmes-story01";
import { initialiseLoadSection } from "./load.js?v=20260404-programmes-story01";
import { renderStoryBanner } from "./narratives.js?v=20260404-programmes-story01";
import { initialisePerformanceSection } from "./performance.js?v=20260404-programmes-story01";
import { initialiseQualitySection } from "./quality.js?v=20260404-programmes-story01";
import { initialiseRegisterInteractions } from "./register.js?v=20260404-programmes-story01";

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

export const initialiseProgrammePage = () => {
    const context = createProgrammeContext();

    if (!context.elements.storyBanner) {
        return;
    }

    renderStoryBanner(
        context.elements.storyBanner,
        context.data.topLoadRows,
        context.data.departmentRows,
        context.data.lowPassRows,
    );

    const controllers = [
        initialiseLoadSection(context),
        initialiseDepartmentSection(context),
        initialiseQualitySection(context),
        initialisePerformanceSection(context),
    ];

    const resizeCharts = () => {
        controllers.forEach((controller) => {
            controller.resize();
        });
    };

    initialiseChartResizeHandling(controllers, resizeCharts);
    initialiseRegisterInteractions(context.elements.searchForm, context.elements.searchInput);
    initialiseFullscreenControls(context.elements.fullscreenButtons, resizeCharts);
};
