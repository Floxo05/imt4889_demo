# Prompt given to the agent

## Where the user stories come from

The 7 user stories were **not written by hand**. They are the unedited answer of Kimi K2.6 (chat, 23 Oct 2026) to the requirements prompt of the lecture, with three extra wishes added by the lecturer:

```text
We are building a small web portal for our university course. Students upload their lecture slides and their peer reviews, and the lecturer can view and download them.
Also:
- The lecturer can leave feedback on each submission
- It works on a phone
- Uploads are done in under 10 seconds
Write the user stories with acceptance criteria.
```

The extra wishes became US-5 (feedback), US-6 (phone) and US-7 (speed). Everything else, including every acceptance criterion, was decided by the AI.

## The prompt for the agent

Sent once, in an empty folder. The agent asked no questions.

```text
We are building a web portal for our university course. Students upload their lecture slides and their peer reviews, and the lecturer can view and download them. Below are our user stories with acceptance criteria.

Build the complete application in this folder with Python and Flask, so that we can use it in our course. First write your implementation plan to PLAN.md, then implement it. Add a README.md that explains how to start the app, and create a few demo accounts (one lecturer, three students) so we can try it out.

### **US-1: Upload Lecture Slides**
*As a student, I want to upload my lecture slide files so that I can submit my coursework before the deadline.*

**Acceptance Criteria**
- **File validation:** Given I am a logged-in student, when I choose a file of type PDF, PPTX, or PPT (up to 50 MB), then the system accepts it for upload and rejects unsupported types with an inline error.
- **Speed:** Given a standard university Wi-Fi connection (10 Mbps), when I tap "Submit", then the system receives the file and displays a success confirmation within 10 seconds.
- **Record:** Given the upload succeeds, when I view my dashboard, then I see the file name, upload timestamp, and a status indicator showing "Submitted".
- **Mobile upload:** Given I am using a smartphone, when I initiate an upload, then I can select files from local or cloud storage and a progress indicator remains visible above the on-screen keyboard.

### **US-2: Upload Peer Review**
*As a student, I want to upload a peer review for an assigned lecture slide submission so that I can fulfill my course participation requirements.*

**Acceptance Criteria**
- **Linked assignment:** Given I am a logged-in student, when I open a peer assignment I have been allocated, then I see an "Upload Peer Review" control prior to the deadline.
- **Speed & confirmation:** Given I attach a valid review file, when I submit it, then the document is linked to that specific peer's submission and I see a confirmation message within 10 seconds.
- **Read-only after deadline:** Given the peer review deadline has passed, when I view the assignment, then my uploaded review is locked and cannot be edited or deleted by me.
- **Lecturer visibility:** Given a peer review is uploaded, when the lecturer views the associated slide submission, then the review document appears in a clearly marked "Peer Reviews" section.

### **US-3: View Submissions (Lecturer)**
*As a lecturer, I want to view all uploaded lecture slides and their associated peer reviews so that I can monitor student progress and participation.*

**Acceptance Criteria**
- **Dashboard list:** Given I am a logged-in lecturer, when I open the course page, then I see a sortable list of all student slide submissions showing student name, submission date, and a count of received peer reviews.
- **Detail view:** Given I select a submission from the list, when the detail page loads, then I can preview the slide deck inline and see a list of all attached peer review documents by reviewer alias/ID.
- **Mobile layout:** Given I am on a phone, when I view the dashboard or a detail page, then the content reflows to fit the screen width without horizontal scrolling and tables stack into cards if necessary.

### **US-4: Download Submissions (Lecturer)**
*As a lecturer, I want to download any submission or peer review document so that I can archive files or review them offline.*

**Acceptance Criteria**
- **Individual download:** Given I am viewing a slide deck or peer review, when I tap the download button, then the original file is saved to my device with its original filename and extension preserved.
- **Batch selection (optional):** Given I am on the submission list, when I select multiple submissions and choose "Download", then a ZIP archive containing those files is generated and downloaded.
- **Mobile hand-off:** Given I am on a smartphone, when a download completes, then the browser hands the file to the device's native share sheet or downloads folder.
- **Background tolerance:** Given I am on a slow mobile connection, when I download a large file, then a progress indicator is shown and the download continues if I switch browser tabs.

### **US-5: Leave Feedback on Submission**
*As a lecturer, I want to leave feedback on each lecture slide submission so that students receive actionable guidance on their work.*

**Acceptance Criteria**
- **Add & save:** Given I am viewing a slide submission detail page, when I enter text into the feedback field and tap "Save Feedback", then the comment is persisted, timestamped, and immediately displayed on the page.
- **Student visibility:** Given I have saved feedback on a submission, when the submitting student views that submission, then they see the lecturer's feedback prominently displayed below the document preview.
- **Edit/Delete:** Given I have previously saved feedback, when I reopen the submission, then I can edit or delete my comment, and students see the updated version immediately upon refresh.
- **Mobile input:** Given I am on a phone, when I focus the feedback text area, then the virtual keyboard does not obscure the save button and the text area remains scrollable.

### **US-6: Access Portal on a Phone**
*As a user, I want the portal to be fully functional on my smartphone so that I can submit or assess work without needing a desktop computer.*

**Acceptance Criteria**
- **Responsive breakpoints:** Given I access the portal from a mobile browser (iOS Safari or Android Chrome), when I navigate through upload, view, download, and feedback flows, then the layout adapts to a viewport width of 320 px–428 px without requiring horizontal scroll or pinch-to-zoom.
- **Touch targets:** Given I am on a touchscreen device, when I interact with any button, link, or file selector, then all targets are at least 44 × 44 density-independent pixels with adequate spacing.
- **Orientation support:** Given I rotate my phone from portrait to landscape, when the orientation changes, then critical controls (upload button, save feedback, download link) remain accessible without being cropped.

### **US-7: Fast Upload Performance**
*As a student, I want my file uploads to complete quickly so that I can confidently submit my work without timeout anxiety.*

**Acceptance Criteria**
- **10-second threshold:** Given a file size of up to 20 MB on a 10 Mbps network with <50 ms latency, when a student initiates an upload, then the server acknowledges receipt and the UI displays a success state within 10 seconds.
- **Progress feedback:** Given an upload is in progress, when the transfer exceeds 2 seconds, then an animated progress bar (percentage or time remaining) is displayed to the user.
- **Timeout handling:** Given network speed drops below the threshold, when an upload is in progress, then the connection remains open for at least 30 seconds before failing, and the user receives a meaningful error message (not a generic timeout).
- **Client-side optimisation:** Given the upload form, when a file is selected, then type and size validation runs client-side before transmission begins to avoid wasting transfer time on invalid files.

```
