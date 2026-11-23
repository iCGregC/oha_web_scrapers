import csv
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.support.ui import WebDriverWait


PAGE_URL = (
    "https://www.ed.gov/laws-and-policy/hearings-and-appeals/"
    "hearings-and-appeals-secretary-decisions"
)

FOLDER = Path(__file__).resolve().parent
OUTPUT_PATH = FOLDER / "oha_secretary_decisions.csv"
DEBUG_FOLDER = FOLDER / "oha_secretary_debug"

CSV_COLUMNS = [
    "Year",
    "Docket Number",
    "Recipient",
    "Topic",
    "Date",
    "View Document",
]


# Find the initialized Secretary Decisions DataTable,
# clear filters, and retrieve every row.
READ_ALL_ROWS_SCRIPT = """
let tables = [];

if (
    window.jQuery &&
    window.jQuery.fn &&
    window.jQuery.fn.dataTable
) {
    tables = Array.from(window.jQuery.fn.dataTable.tables());
} else if (
    window.DataTable &&
    typeof window.DataTable.tables === "function"
) {
    tables = Array.from(window.DataTable.tables());
}

for (const table of tables) {
    let api;

    if (
        window.jQuery &&
        window.jQuery.fn &&
        window.jQuery.fn.dataTable
    ) {
        api = window.jQuery(table).DataTable();
    } else {
        api = new window.DataTable.Api(table);
    }

    const headings = Array.from(
        table.querySelectorAll("thead th, thead td")
    ).map(cell => cell.textContent.trim().toLowerCase());

    const headingText = headings.join(" ");

    const matchesHeadings =
        headingText.includes("docket") &&
        headingText.includes("recipient") &&
        headingText.includes("topic");

    // Fallback for tables whose headings are rendered separately.
    const sampleRows = api.rows().nodes().toArray().slice(0, 10);

    const matchesRows = sampleRows.some(row => {
        const cells = row.querySelectorAll("td");

        return (
            cells.length === 6 &&
            /^\\d{4}$/.test(cells[0].textContent.trim()) &&
            cells[5].querySelector("a[href]")
        );
    });

    if (!matchesHeadings && !matchesRows) {
        continue;
    }

    const settings = api.settings()[0];

    if (settings.oFeatures.bServerSide) {
        return {
            error:
                "This table uses server-side pagination. " +
                "This script cannot confirm a full export."
        };
    }

    api.search("");
    api.columns().search("");
    api.page.len(-1).draw();

    const info = api.page.info();

    return {
        total: info.recordsTotal,
        html: api.rows({
            search: "none",
            page: "all"
        }).nodes().toArray().map(
            row => row.outerHTML
        ).join("")
    };
}

return null;
"""


def extract_records(html):
    """Preserve every source row without docket-format filtering."""
    soup = BeautifulSoup(
        "<table>" + html + "</table>",
        "html.parser",
    )

    records = []

    for index, row in enumerate(soup.find_all("tr"), start=1):
        cells = row.find_all(["td", "th"], recursive=False)

        if len(cells) != 6:
            raise RuntimeError(
                f"Source row {index} has {len(cells)} columns "
                f"instead of 6. Row text: "
                f"{row.get_text(' ', strip=True)!r}"
            )

        year = cells[0].get_text(" ", strip=True)
        docket = cells[1].get_text(" ", strip=True)
        recipient = cells[2].get_text(" ", strip=True)
        topic = cells[3].get_text(" ", strip=True)
        decision_date = cells[4].get_text(" ", strip=True)

        urls = []

        for link in cells[5].find_all("a", href=True):
            href = link["href"].strip()

            if not href or href.lower().startswith(
                ("#", "javascript:")
            ):
                continue

            absolute_url = urljoin(PAGE_URL, href)

            # Ignore duplicate anchors pointing to the same document.
            if absolute_url not in urls:
                urls.append(absolute_url)

        if len(urls) > 1:
            raise RuntimeError(
                f"Row {index}, docket {docket!r}, contains "
                f"multiple different document links: {urls}. "
                "Stopped to avoid losing a document."
            )

        document_url = urls[0] if urls else ""

        if not docket or not recipient or not document_url:
            print(
                f"REVIEW row {index}: "
                f"docket={docket!r}, "
                f"recipient={recipient!r}, "
                f"document_url={document_url!r}"
            )

        records.append({
            "Year": year,
            "Docket Number": docket,
            "Recipient": recipient,
            "Topic": topic,
            "Date": decision_date,
            "View Document": document_url,
        })

    return records


def save_diagnostics(driver):
    """Save the current page if scraping fails."""
    DEBUG_FOLDER.mkdir(exist_ok=True)

    (DEBUG_FOLDER / "page.html").write_text(
        driver.page_source,
        encoding="utf-8",
    )

    driver.save_screenshot(
        str(DEBUG_FOLDER / "page.png")
    )

    print("Diagnostics saved to:", DEBUG_FOLDER)


def main():
    options = webdriver.ChromeOptions()
    options.add_argument("--window-size=1400,1000")

    # Keep Chrome visible. Do not close it while the script runs.
    driver = webdriver.Chrome(options=options)

    try:
        driver.get(PAGE_URL)

        print("Page title:", driver.title)
        print("Current URL:", driver.current_url)
        print("Waiting for the Secretary Decisions table...")

        result = WebDriverWait(driver, 60).until(
            lambda browser: browser.execute_script(
                READ_ALL_ROWS_SCRIPT
            )
        )

        if result.get("error"):
            raise RuntimeError(result["error"])

        expected = int(result["total"])

        if expected <= 0:
            raise RuntimeError(
                "The website reported no records."
            )

        records = extract_records(result["html"])

        print("Website total:", expected)
        print("Extracted records:", len(records))

        if len(records) != expected:
            raise RuntimeError(
                f"Count mismatch: expected {expected}, "
                f"extracted {len(records)}. "
                "No new CSV was written."
            )

        with OUTPUT_PATH.open(
            "w",
            newline="",
            encoding="utf-8-sig",
        ) as output:
            writer = csv.DictWriter(
                output,
                fieldnames=CSV_COLUMNS,
            )
            writer.writeheader()
            writer.writerows(records)

        print(
            f"\nSUCCESS: Exported {len(records)} records."
        )
        print("CSV saved to:", OUTPUT_PATH)

    except Exception as error:
        print(
            f"\nFAILED: {type(error).__name__}: {error}"
        )

        try:
            save_diagnostics(driver)
        except Exception as diagnostic_error:
            print(
                "Could not save diagnostics:",
                diagnostic_error,
            )

        print(
            "Any CSV from a previous run is unchanged. "
            "Do not mistake it for a successful new export."
        )

    finally:
        try:
            driver.quit()
        except Exception:
            pass


if __name__ == "__main__":
    main()