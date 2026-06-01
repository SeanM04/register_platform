// Import home page modal functions for consistency
import { 
    isDrillDownModalOpen as isHomeDrillDownModalOpen,
    closeDrillDownModal as closeHomeDrillDownModal,
    showDrillDownErrorModal as showHomeDrillDownErrorModal,
    showLoadingDrillDownModal as showHomeLoadingDrillDownModal,
    showDrillDownModal as showHomeDrillDownModal
} from "../home/drilldown_modal.js?v=20260601-drilldown-numeric-align01";

// Re-export with graduation names for backward compatibility
export const isDrillDownModalOpen = isHomeDrillDownModalOpen;
export const closeDrillDownModal = closeHomeDrillDownModal;
export const showDrillDownErrorModal = showHomeDrillDownErrorModal;
export const showLoadingDrillDownModal = showHomeLoadingDrillDownModal;
export const showDrillDownModal = showHomeDrillDownModal;

export const showGraduationDrillDownModal = (payload, onPageChange = null) => {
    const pagination = payload.pagination || {};
    // Transform graduation payload to match home page format
    const transformedPayload = {
        title: payload.title || "Student Details",
        subtitle: payload.subtitle || `Showing ${payload.total_items || payload.total_count || pagination.total_items || 0} students`,
        columns: payload.columns || [],
        rows: payload.rows || [],
        total_items: payload.total_items || payload.total_count || pagination.total_items || 0,
        current_page: payload.current_page || payload.page || pagination.current_page || 1,
        page_size: payload.page_size || pagination.page_size || 10,
        total_pages: payload.total_pages || payload.page_count || pagination.total_pages || 1,
    };
    
    // Use home page modal with transformed payload
    return showHomeDrillDownModal(transformedPayload, [], { onPageChange });
};
