📑 Final Project Specification
Root Project Structure
project_root/
├─ scraper.py          # Program 1
├─ deduplicate.py      # Program 2
├─ evaluator.py        # Program 3
│
└─ data/
   ├─ queries/         # Input files for Program 1
   ├─ maps/            # Output of Program 1
   ├─ combined/        # Output of Program 2
   └─ results/         # Output of Program 3


Each program knows its folders. No need to pass folder paths via args.

1️⃣ Program 1 – Scraper (scraper.py)
Purpose

Scrape businesses from Google Maps queries listed in .xlsx files.

Input

.xlsx files in ./data/queries/

Each file contains rows with:

query_url (Google Maps search link)

status (empty = pending, or one of success|error|pending)

CLI
python scraper.py file1.xlsx,file2.xlsx
# or single file
python scraper.py file1.xlsx
# force re-scrape everything in the files
python scraper.py file1.xlsx,file2.xlsx --rescrape


Input: file names only, comma-separated (no folder path).

Program automatically looks in ./data/queries/.

Output always goes into ./data/maps/.

Process

For each input file:

Read all rows.

If --rescrape is not used:

Skip rows with status=success.

Process rows where status is empty, pending, or error.

If --rescrape is used:

Re-process all rows from scratch.

For each query:

Launch Playwright.

Scroll Google Maps until no new results.

Extract businesses (via script JSON when possible).

Extracted Fields (columns in output):

position (int, or list if duplicate merging later)

name

categories

website

phone

email

address

description

reviews_count

rating

listing_link

has_image (True/False)

status (success|error|pending)

source_file (the queries file this row came from)

Output

For each query in the input file:

A separate .xlsx in ./data/maps/

Filename derived deterministically from the query text in the Google Maps URL.

Same query → same filename every time (no randomness).

Examples:

https://www.google.com/maps/search/plumbers+denver → maps/plumbers denver.xlsx

https://www.google.com/maps/search/?q=roofers+aurora → maps/roofers aurora.xlsx

Logging (terminal)

For each query row:

[✓] Success: plumbers denver (34 results)
[!] Error: roofers aurora (timeout)
[⏸] Pending: electricians boulder (interrupted)
[→] Skipped: hvac denver (already success)


Summary after finishing a file:

Finished file plumbers_queries.xlsx
Success: 25 | Error: 2 | Pending: 1 | Skipped: 15

2️⃣ Program 2 – Deduplicator & Merger (deduplicate.py)
Purpose

Merge multiple scraped map files into a deduplicated combined file.

Input

.xlsx files from ./data/maps/

CLI
python deduplicate.py file1.xlsx,file2.xlsx


Input = filenames only, comma-separated.

Program automatically looks inside ./data/maps/.

Process

Load all input map files.

Deduplicate businesses by listing_link.

If duplicate, merge position values into a list, e.g. [1,7].

Track source files → add columns query_filename1, query_filename2, etc.

Add status column (pending by default).

Update input map files with statuses (e.g., mark rows as success if included).

Output

One combined file in ./data/combined/.

Filename = all input filenames joined with __ (deterministic).

Example:

deduplicate.py plumbers denver.xlsx,roofers aurora.xlsx
→ ./data/combined/plumbers denver__roofers aurora.xlsx

3️⃣ Program 3 – Evaluator (evaluator.py)
Purpose

Semi-automated evaluation of businesses with Tkinter GUI + Playwright.

Input

.xlsx files from ./data/combined/

CLI
python evaluator.py file1.xlsx,file2.xlsx


Input = filenames only, comma-separated.

Program automatically looks inside ./data/combined/.

GUI Behavior

For each row:

Show all data (name, address, website, phone, reviews, etc.).

Open the business website in Playwright browser (if available).

Rating buttons: Good / Okay / Bad.

Control: Next (go to next row).

Keyboard shortcuts: g=Good, o=Okay, b=Bad, n=Next.

Saving

As you rate each business:

Append row to results file in ./data/results/.

Results filename = same as input filename.

Add columns: rating, eval_time, (optional notes).

Update the parent combined file status for that row.

Output

/data/results/[input_filename].xlsx

Example:

evaluator.py plumbers denver__roofers aurora.xlsx
→ ./data/results/plumbers denver__roofers aurora.xlsx

✅ Final Notes

Status rules are consistent: success | error | pending (empty = pending).

No randomness in filenames. Same input always → same output.

Programs know their folders:

Scraper: queries → maps

Deduplicator: maps → combined

Evaluator: combined → results

Args = filenames only, comma-separated.

Resumable: Programs skip successes unless --rescrape is used.


Google Maps Lead Finder Project

Tech Stack: Python, Playwright, Tkinter, BeautifulSoup4, Requests (optional), OpenPyXL

This project is one root folder with 3 coordinated programs that share the same folder structure.

root/
 ├── scraper.py
 ├── deduplicator.py
 ├── evaluator.py
 └── data/
      ├── queries/
      │    └── [query-files].xlsx
      ├── maps/
      │    └── [query-slug].xlsx
      ├── combined/
      │    └── [combined-filenames].xlsx
      └── results/
           └── [evaluated-filenames].xlsx

1. Scraper (scraper.py)
Purpose

Takes input query files, visits Google Maps links, scrolls to load all results, extracts business details, and saves them into structured .xlsx files.

Input

Files located in ./data/queries/

Passed as arguments:

python scraper.py file1.xlsx,file2.xlsx


Each query file must contain:

link (Google Maps search URL)

status (success | error | pending | empty)

empty = same as pending (no value)

Output

Saves results to ./data/maps/[query-slugified].xlsx

Slug is extracted from the Google Maps query parameter (not random).

Output columns per business:

name

address

website

phone

categories

description

review_count

review_rating

listing_link

has_image (yes/no)

position (rank in results)

status (success | error | pending | empty)

Behavior

Reads each row in the query file.

Skips rows with success unless --rescrape flag is used.

Logs progress in the terminal (scraped X businesses, skipped Y, error on Z).

If stopped mid-run → all unfinished rows marked as pending.

Errors are logged and marked as error.

Arguments
python scraper.py file1.xlsx,file2.xlsx [--rescrape]

2. Deduplicator (deduplicator.py)
Purpose

Combines multiple scraped maps files, removes duplicates, and outputs a merged .xlsx.

Input

Files located in ./data/maps/

Passed as arguments:

python deduplicator.py file1.xlsx,file2.xlsx

Output

Combined file is written to ./data/combined/

Output filename is deterministic and based on input names:

file1_file2.xlsx


Output columns:

All columns from scraper

positions → a list of positions from different files, e.g. [1, 7]

query_sources → names of input files where business appeared

status (success | error | pending | empty)

Behavior

If duplicate businesses are found (same listing_link):

Keep one entry

Merge their position values into a list

Track sources (file1, file2, …)

If no duplicates: position still becomes a list (e.g. [5])

Writes back updated statuses into input files as well.

3. Evaluator (evaluator.py)
Purpose

Human-in-the-loop tool to review businesses from combined files.

Input

Files located in ./data/combined/

Passed as arguments:

python evaluator.py file1_file2.xlsx

Output

Saves evaluated rows to ./data/results/[same-filename].xlsx

Behavior

Opens a Tkinter window + Playwright browser instance.

Iterates row by row from the combined file.

Displays in Tkinter:

All extracted business data (name, address, website, categories, reviews, etc.)

Control buttons:

Good

Okay

Bad

Next

Saves rating into results file under column evaluation

Updates parent combined file’s status accordingly.

Progress is row by row (if closed, work can resume later).

Summary of Folder Logic

Input folders: fixed (queries, maps, combined)

Output folders: fixed (maps, combined, results)

File naming:

Deterministic → based on input file names or query slug.

No randomness.

Same inputs always produce same output filename.