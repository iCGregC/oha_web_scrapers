import csv
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.support.ui import WebDriverWait


PAGE_URL = (
    "https://www.ed.gov/about/doing-business-ed/working-ed/"
    "onboarding-documents/salary-overpayment-matters-ed/"
    "salary-overpayments-waiver-and-offset-decisions"
)

FOLDER = Path(__file__).resolve().parent
OUTPUT_PATH = FOLDER / "oha_salary_overpayment_decisions.csv"
DEBUG_FOLDER = FOLDER / "oha_salary_overpayment_debug"

CSV_COLUMNS = [
    "Year",
    "Docket Number",
    "Respondent",
    "View Decision",
]


# Find the initialized DataTable and retrieve every source row.
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
        headingText.includes("year") &&
        headingText.includes("docket") &&
        headingText.includes("respondent");

    // Fallback if headings are rendered in a separate table.
    const sampleRows = api.rows().nodes().toArray().slice(0, 10);

    const matchesRows = sampleRows.some(row => {
        const cells = row.querySelectorAll("td");

        return (
            cells.length === 4 &&
            /^\\d{4}$/.test(cells[0].textContent.trim()) &&
            cells[3].querySelector("a[href]")
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
    """Preserve every row without filtering docket formats."""
    soup = BeautifulSoup(
        "<table>" + html + "</table>",
        "html.parser",
    )

    records = []

    for index, row in enumerate(soup.find_all("tr"), start=1):
        cells = row.find_all(["td", "th"], recursive=False)

        if len(cells) != 4:
            raise RuntimeError(
                f"Source row {index} has {len(cells)} columns "
                f"instead of 4. Row text: "
                f"{row.get_text(' ', strip=True)!r}"
            )

        year = cells[0].get_text(" ", strip=True)
        docket = cells[1].get_text(" ", strip=True)
        respondent = cells[2].get_text(" ", strip=True)

        urls = []

        for link in cells[3].find_all("a", href=True):
            href = link["href"].strip()

            if not href or href.lower().startswith(
                ("#", "javascript:")
            ):
                continue

            absolute_url = urljoin(PAGE_URL, href)

            # Ignore duplicate anchors for the same document.
            if absolute_url not in urls:
                urls.append(absolute_url)

        if len(urls) > 1:
            raise RuntimeError(
                f"Row {index}, docket {docket!r}, contains "
                f"multiple different document links: {urls}. "
                "Stopped to avoid losing a document."
            )

        document_url = urls[0] if urls else ""

        if not year or not docket or not respondent or not document_url:
            print(
                f"REVIEW row {index}: "
                f"year={year!r}, "
                f"docket={docket!r}, "
                f"respondent={respondent!r}, "
                f"document_url={document_url!r}"
            )

        records.append({
            "Year": year,
            "Docket Number": docket,
            "Respondent": respondent,
            "View Decision": document_url,
        })

    return records


def save_diagnostics(driver):
    """Save the browser page if scraping fails."""
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

    # Leave Chrome open while the script runs.
    driver = webdriver.Chrome(options=options)

    try:
        driver.get(PAGE_URL)

        print("Page title:", driver.title)
        print("Current URL:", driver.current_url)
        print("Waiting for the salary overpayment decisions table...")

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

        # Write to a temporary file first, then replace the output.
        # This avoids leaving a partially written final CSV.
        temporary_path = OUTPUT_PATH.with_suffix(".csv.tmp")

        with temporary_path.open(
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

        temporary_path.replace(OUTPUT_PATH)

        print(f"\nSUCCESS: Exported {len(records)} records.")
        print("CSV saved to:", OUTPUT_PATH)

    except Exception as error:
        print(f"\nFAILED: {type(error).__name__}: {error}")

        try:
            save_diagnostics(driver)
        except Exception as diagnostic_error:
            print(
                "Could not save diagnostics:",
                diagnostic_error,
            )

        print(
            "No successful new export was completed. "
            "Any final CSV from a previous run is unchanged."
        )

    finally:
        try:
            driver.quit()
        except Exception:
            pass


if __name__ == "__main__":
    main()