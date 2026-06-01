/**
 * Drilldown modal functionality for demographic charts.
 * Uses the same design as home page drilldown.
 */

// Import the home page modal functions
import { 
    isDrillDownModalOpen as isHomeDrillDownModalOpen,
    closeDrillDownModal as closeHomeDrillDownModal,
    showDrillDownErrorModal as showHomeDrillDownErrorModal,
    showLoadingDrillDownModal as showHomeLoadingDrillDownModal,
    showDrillDownModal as showHomeDrillDownModal
} from "../home/drilldown_modal.js?v=20260601-drilldown-numeric-align01";

// Re-export with demographic names
export const isDrillDownModalOpen = isHomeDrillDownModalOpen;
export const closeDrillDownModal = closeHomeDrillDownModal;
export const showDrillDownErrorModal = showHomeDrillDownErrorModal;
export const showLoadingDrillDownModal = showHomeLoadingDrillDownModal;

export const showDrillDownModal = (payload, chartData = {}, options = {}) => {
    // Transform demographic payload to match home page format
    const transformedPayload = {
        ...payload,
        title: payload.title || payload.bucket_label || "Student Details",
        subtitle: payload.subtitle || `Showing ${payload.total_count || 0} students`,
        columns: payload.columns || [],
        rows: payload.rows || [],
        data: payload.data || [],
        type: payload.type || "students",
        total_count: payload.total_count || 0,
        page: payload.page || 1,
        page_size: payload.page_size || 10,
        page_count: payload.page_count || 1,
        breadcrumbs: payload.breadcrumbs || [],
    };
    
    // Use home page modal with transformed payload
    return showHomeDrillDownModal(transformedPayload, chartData, options);
};
