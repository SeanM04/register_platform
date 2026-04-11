# Drill-Down Modal and Pagination Frontend

## Overview

The drill-down modal provides an accessible, responsive interface for browsing paginated student lists from chart clicks on the landing dashboard.

## Files

- `dashboard/static/dashboard/js/home/drilldown.js` – Orchestrates drill-down requests and page navigation
- `dashboard/static/dashboard/js/home/drilldown_modal.js` – Renders modal UI and pagination table
- `dashboard/static/dashboard/css/home.css` – Modal and pagination styling

## Architecture

### Data Flow

```
User clicks chart
    ↓
openOverviewDrillDown(context, {chartKey, bucketKey, label})
    ↓
showLoadingDrillDownModal() [show "Loading..." spinner]
    ↓
loadPage(page, pageSize)
    ↓
fetchDrillDownPayload(endpoint, {chart, bucket, page, page_size})
    ↓
Backend caching + filtering
    ↓
showDrillDownModal(payload, [], {onPageChange, onPageSizeChange})
    ↓
Modal renders table + pagination controls
    ↓
User clicks Prev/Next or closes modal
```

## Component: drilldown.js

**Purpose**: Fetch and load drill-down data, manage page requests, handle errors.

### Key Function: `openOverviewDrillDown()`

```javascript
export const openOverviewDrillDown = async (context, { chartKey, bucketKey, label }) => {
  cancelOverviewDrillDownRequests();

  let currentPageSize = DEFAULT_DRILLDOWN_PAGE_SIZE; // 100
  const requestToken = activeOverviewDrillDownToken;
  const safeLabel = String(label || "Selected").trim() || "Selected";
  const title = `${safeLabel} Students`;
  const subtitle = `Loading the students in the ${safeLabel.toLowerCase()} selection.`;
  const endpoint = context?.config?.drilldownUrl;

  if (!endpoint || !chartKey || !bucketKey) {
    showDrillDownErrorModal(title, "This chart drill-down is not available right now.");
    return;
  }

  showLoadingDrillDownModal(title, subtitle);

  const loadPage = async (page, pageSize = currentPageSize) => {
    currentPageSize = pageSize || DEFAULT_DRILLDOWN_PAGE_SIZE;
    showLoadingDrillDownModal(title, subtitle);

    try {
      const payload = await fetchDrillDownPayload(endpoint, {
        chart: chartKey,
        bucket: bucketKey,
        page,
        page_size: currentPageSize,
      });

      if (requestToken !== activeOverviewDrillDownToken || !isDrillDownModalOpen()) {
        return;
      }

      showDrillDownModal(payload, [], {
        onPageChange: loadPage,
        onPageSizeChange: (newPageSize) => loadPage(1, newPageSize),
      });
    } catch (error) {
      // Handle error...
      showDrillDownErrorModal(title, `Could not load...`);
    }
  };

  try {
    await loadPage(1, currentPageSize);
  } catch (error) {
    showDrillDownErrorModal(title, `Could not load...`);
  }
};
```

**Features**:
- **Request cancellation**: `cancelOverviewDrillDownRequests()` increments token to ignore stale requests
- **Loading state**: Shows spinner while data is fetching
- **Error handling**: Falls back to error modal if requests fail
- **Page navigation**: `loadPage()` callback handles both page changes and page-size changes
- **Page-size reset**: Changing page size resets to page 1

### Constants

```javascript
const DEFAULT_DRILLDOWN_PAGE_SIZE = 100;
let activeOverviewDrillDownToken = 0;
```

## Component: drilldown_modal.js

**Purpose**: Render accessible modal with table, pagination controls, and event handlers.

### Build Functions

#### `buildTableBodyHtml(payload)`

Renders the three-column table from drill-down payload:

```javascript
const headerHtml = columns.map((column) => `
  <th scope="col">${escapeTooltipHtml(column?.label || column?.key || "Column")}</th>
`).join("");

const rowsHtml = rows.length
  ? rows.map((row) => {
      const cellsHtml = columns.map((column, columnIndex) => {
        const cellValue = escapeTooltipHtml(getDisplayValue(row?.[column.key]));
        const detailUrl = String(row?.detail_url || "").trim();
        if (columnIndex === 0 && detailUrl) {
          return `<td><a class="home-drilldown-link" href="${detailUrl}">${cellValue}</a></td>`;
        }
        return `<td>${cellValue}</td>`;
      }).join("");
      return `<tr>${cellsHtml}</tr>`;
    }).join("")
  : `<tr><td class="home-drilldown-empty" colspan="${columns.length}">No students matched.</td></tr>`;

return `
  <div class="home-drilldown-table-wrap">
    <table class="home-drilldown-table">
      <thead><tr>${headerHtml}</tr></thead>
      <tbody>${rowsHtml}</tbody>
    </table>
  </div>
  ${buildPaginationHtml(payload)}
`.trim();
```

**Features**:
- First column (student name) is a clickable link to student detail page
- Empty state shows when no rows match
- Pagination HTML appended below table

#### `buildPaginationHtml(payload)`

Renders pagination info and controls:

```javascript
const buildPaginationHtml = (payload = {}) => {
  const page = Number(payload.page) || 1;
  const pageSize = Number(payload.page_size) || 100;
  const totalCount = Number(payload.total_count) || 0;
  const pageCount = Number(payload.page_count) || 1;

  const sizeInfoHtml = `
    <div class="home-drilldown-page-size-pill">${pageSize} rows per page</div>
  `.trim();

  const previousDisabled = page <= 1 ? "disabled" : "";
  const nextDisabled = page >= pageCount ? "disabled" : "";

  return `
    <div class="home-drilldown-pagination">
      ${sizeInfoHtml}
      <div class="home-drilldown-pagination-controls">
        <button class="home-drilldown-pagination-button" type="button" data-drilldown-page="${page - 1}" ${previousDisabled}>Prev</button>
        <span class="home-drilldown-pagination-info">Page ${page} of ${pageCount}</span>
        <button class="home-drilldown-pagination-button" type="button" data-drilldown-page="${page + 1}" ${nextDisabled}>Next</button>
      </div>
    </div>
  `.trim();
};
```

**Features**:
- Static "100 rows per page" pill (no dropdown selector)
- Page/Total display (e.g., "Page 2 of 5")
- Prev button disabled on first page
- Next button disabled on last page

### Modal Rendering

#### `renderModal()`

Creates and displays the modal DOM:

```javascript
const renderModal = ({ title, subtitle = "", bodyHtml, toneClass = "", onPageChange = null, onPageSizeChange = null }) => {
  closeDrillDownModal();
  lastFocusedElement = document.activeElement instanceof HTMLElement ? document.activeElement : null;

  const modal = document.createElement("div");
  modal.id = DRILLDOWN_MODAL_ID;
  modal.className = "home-drilldown-modal";
  modal.innerHTML = `
    <div class="home-drilldown-dialog ${toneClass}" role="dialog" aria-modal="true" aria-labelledby="home-drilldown-title">
      <div class="home-drilldown-header">
        <div class="home-drilldown-heading">
          <h2 class="home-drilldown-title" id="home-drilldown-title">${escapeTooltipHtml(title)}</h2>
          <p class="home-drilldown-subtitle" id="home-drilldown-subtitle">${escapeTooltipHtml(subtitle)}</p>
        </div>
        <button class="home-drilldown-close" type="button" data-drilldown-close aria-label="Close">Close</button>
      </div>
      <div class="home-drilldown-body">${bodyHtml}</div>
    </div>
  `.trim();

  // Attach event listeners
  modal.addEventListener("click", (event) => {
    if (event.target === modal) closeDrillDownModal();
  });

  const closeButton = modal.querySelector("[data-drilldown-close]");
  if (closeButton) {
    closeButton.addEventListener("click", () => closeDrillDownModal());
  }

  const pageButtons = modal.querySelectorAll("[data-drilldown-page]");
  if (typeof onPageChange === "function" && pageButtons.length) {
    pageButtons.forEach((button) => {
      button.addEventListener("click", () => {
        const pageValue = Number(button.dataset.drilldownPage);
        if (!Number.isNaN(pageValue)) {
          onPageChange(pageValue);
        }
      });
    });
  }

  const pageSizeSelect = modal.querySelector("[data-drilldown-page-size]");
  if (typeof onPageSizeChange === "function" && pageSizeSelect instanceof HTMLSelectElement) {
    pageSizeSelect.addEventListener("change", () => {
      const selectedValue = Number(pageSizeSelect.value);
      if (!Number.isNaN(selectedValue) && selectedValue > 0) {
        onPageSizeChange(selectedValue);
      }
    });
  }

  document.body.appendChild(modal);
  document.body.classList.add("has-home-drilldown-modal");
  document.addEventListener("keydown", handleEscapeKey);

  const dialog = modal.querySelector(".home-drilldown-dialog");
  if (dialog instanceof HTMLElement) {
    dialog.focus();
  }
};
```

**Accessibility Features**:
- `role="dialog"`, `aria-modal="true"` for screen readers
- `aria-labelledby` links title
- Modal receives focus on open
- ESC key closes modal
- Prev/Next buttons are proper buttons with visible labels
- Click outside modal closes it

## Styling

### CSS Classes

Located in `dashboard/static/dashboard/css/home.css`:

| Class | Purpose |
|-------|---------|
| `.home-drilldown-modal` | Outer container, darkens background |
| `.home-drilldown-dialog` | Modal card with rounded corners, white background |
| `.home-drilldown-header` | Title + close button area |
| `.home-drilldown-title` | H2 title |
| `.home-drilldown-subtitle` | Description text |
| `.home-drilldown-close` | Close button |
| `.home-drilldown-body` | Table and pagination container |
| `.home-drilldown-table-wrap` | Wrapper for scrollable table |
| `.home-drilldown-table` | Three-column table |
| `.home-drilldown-link` | Student name link styling |
| `.home-drilldown-pagination` | Flex container for page info + controls |
| `.home-drilldown-page-size-pill` | Static "100 rows per page" display |
| `.home-drilldown-pagination-controls` | Prev/Next button group |
| `.home-drilldown-pagination-button` | Pagination button styling |
| `.home-drilldown-pagination-info` | "Page X of Y" text |

### Button Styling

```css
.home-drilldown-pagination-button {
  min-width: 60px;
  padding: 0.5rem 0.85rem;
  border-radius: 12px;
  border: 1px solid rgba(79, 176, 209, 0.2);
  background: #eef2f7;
  color: #163d69;
  font-weight: 700;
  cursor: pointer;
  transition: background-color 0.2s ease, transform 0.2s ease;
}

.home-drilldown-pagination-button:hover:not(:disabled) {
  background: #dbe9f5;
  transform: translateY(-1px);
}

.home-drilldown-pagination-button:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}
```

## Event Flow

### User Click → Page Load

```
User clicks "Prev" button
    ↓
Click event fires on button with data-drilldown-page="0"
    ↓
pageButtons.forEach(...) event listener triggers
    ↓
Extracts pageValue from button.dataset.drilldownPage
    ↓
Calls onPageChange(pageValue) callback
    ↓
loadPage(pageValue, currentPageSize) called from drilldown.js
    ↓
showLoadingDrillDownModal() shows spinner
    ↓
fetchDrillDownPayload(endpoint, {chart, bucket, page, page_size})
    ↓
showDrillDownModal(payload) with updated table
```

## Error Handling

### Request Cancellation

Prevents stale responses from being displayed:

```javascript
let activeOverviewDrillDownToken = 0;

export const cancelOverviewDrillDownRequests = () => {
  activeOverviewDrillDownToken += 1;
};

const loadPage = async (page, pageSize) => {
  const token = activeOverviewDrillDownToken;
  const payload = await fetchDrillDownPayload(...);
  
  if (token !== activeOverviewDrillDownToken) {
    return; // Ignore stale response
  }
  
  showDrillDownModal(payload);
};
```

### Error Modal

Shows when drill-down fails:

```javascript
export const showDrillDownErrorModal = (title, subtitle = "") => {
  renderModal({
    title,
    subtitle,
    bodyHtml: `
      <div class="home-drilldown-state">
        <p class="home-drilldown-state-title">${escapeTooltipHtml(subtitle)}</p>
      </div>
    `,
    toneClass: "is-error",
  });
};
```

## Testing Considerations

1. **Modal visibility**: Verify modal appears/disappears on click
2. **Pagination**: Test Prev/Next buttons enable/disable correctly
3. **Page loading**: Confirm loadPage callback fires with correct page number
4. **Accessibility**: Test keyboard navigation (Tab, ESC, Enter)
5. **Error states**: Test error modal shows on request failure
6. **Request cancellation**: Verify stale responses are ignored

## Future Enhancements

1. Add search/filter within the modal table
2. Add column sorting
3. Add CSV export button
4. Support variable page sizes via dropdown
5. Add loading progress bar for slow connections
