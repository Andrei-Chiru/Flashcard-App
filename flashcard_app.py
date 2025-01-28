import tkinter as tk
from tkinter import messagebox, ttk, filedialog
import json
import os
import random

# Pillow for images
from PIL import Image, ImageTk
# For Pillow >= 9.1.0, use Resampling instead of Image.ANTIALIAS
from PIL.Image import Resampling

FLASHCARDS_FILE = "flashcards.json"

class FlashcardApp:
    def __init__(self, master):
        self.master = master
        self.master.title("Flashcard Study App - Two Tabs")
        self.master.geometry("900x550")
        self.master.config(bg="#F5F5F5")

        # ------------------------------------------------
        # Internal Data
        # ------------------------------------------------
        # Dictionary of courses -> list of flashcards
        # Each flashcard: {
        #   "question": str,
        #   "answer": str,
        #   "question_img": path_or_None,
        #   "answer_img": path_or_None
        # }
        self.courses = self.load_courses()

        # Current selected course
        self.current_course = None

        # We store the current flashcard's index in self.courses[self.current_course].
        # If None, no card is selected yet.
        self.current_flashcard_index = None

        # For random deck usage without repeats:
        # self.shuffle_bags[course_name] = list of card indices to draw from
        self.shuffle_bags = {}

        # Counters for how many are in the deck and how many we've seen
        self.current_deck_count = 0
        self.current_deck_seen = 0

        # Temporary file paths for new question/answer images in the "Create" tab
        self.new_question_img_path = None
        self.new_answer_img_path = None

        # Keep references to displayed images so Python doesn't garbage-collect them
        self.question_img_obj = None
        self.answer_img_obj = None

        # ------------------------------------------------
        # Build the UI (Notebook with 2 tabs)
        # ------------------------------------------------
        self.notebook = ttk.Notebook(self.master)
        self.notebook.pack(fill="both", expand=True)

        # Two frames (tabs)
        self.tab_create_manage = ttk.Frame(self.notebook)
        self.tab_study = ttk.Frame(self.notebook)

        self.notebook.add(self.tab_create_manage, text="Create & Manage")
        self.notebook.add(self.tab_study, text="Study")

        # Build each tab’s content
        self.build_create_manage_tab()
        self.build_study_tab()

    # ================================================================
    # Build Tab 1: Create & Manage Flashcards
    # ================================================================
    def build_create_manage_tab(self):
        tab = self.tab_create_manage
        tab.config(width=900, height=550)

        # -- Left: Course Management --
        course_frame = tk.LabelFrame(
            tab,
            text=" Course Management ",
            bg="#FFFFFF",
            font=("Helvetica", 20, "bold")
        )
        course_frame.pack(side="left", fill="y", padx=10, pady=10)

        # Add Course
        tk.Label(
            course_frame,
            text="Add a new course:",
            bg="#FFFFFF",
            font=("Helvetica", 20)
        ).pack(pady=(10,0))
        self.new_course_entry = tk.Entry(course_frame, font=("Helvetica", 20))
        self.new_course_entry.pack(pady=5)

        add_course_button = tk.Button(
            course_frame,
            text="Add Course",
            font=("Helvetica", 20),
            command=self.add_new_course
        )
        add_course_button.pack(pady=5)

        ttk.Separator(course_frame, orient="horizontal").pack(fill="x", pady=10)

        # Existing course dropdown
        tk.Label(
            course_frame,
            text="Select a course to manage:",
            bg="#FFFFFF",
            font=("Helvetica", 20)
        ).pack(pady=(5,0))
        self.manage_course_var = tk.StringVar()
        self.manage_course_dropdown = ttk.Combobox(
            course_frame,
            textvariable=self.manage_course_var,
            state="readonly",
            font=("Helvetica", 20)
        )
        self.manage_course_dropdown.pack(pady=5)
        self.update_course_dropdown()
        self.manage_course_dropdown.bind("<<ComboboxSelected>>", self.on_manage_course_selected)

        # # The disabled "Save All Courses to Disk" button
        # save_all_button = tk.Button(
        #     course_frame,
        #     text="Save All Courses to Disk",
        #     font=("Helvetica", 20),
        #     command=self.save_courses_to_disk,
        #     state="disabled"  # <--- Disabled button
        # )
        # save_all_button.pack(pady=20)

        # -- Middle: Create Flashcard --
        create_frame = tk.LabelFrame(
            tab,
            text=" Create a New Flashcard ",
            bg="#FFFFFF",
            font=("Helvetica", 20, "bold")
        )
        create_frame.pack(side="left", fill="both", expand=True, padx=10, pady=10)

        tk.Label(create_frame, text="Question:", bg="#FFFFFF", font=("Helvetica", 20)).pack()
        self.question_entry = tk.Text(create_frame, height=3, width=35, wrap="word", font=("Helvetica", 20))
        self.question_entry.pack(pady=5)

        # Attach question image
        tk.Button(
            create_frame,
            text="Attach Question Image",
            font=("Helvetica", 20),
            command=self.select_question_image
        ).pack(pady=5)

        tk.Label(create_frame, text="Answer:", bg="#FFFFFF", font=("Helvetica", 20)).pack()
        self.answer_entry = tk.Text(create_frame, height=3, width=35, wrap="word", font=("Helvetica", 20))
        self.answer_entry.pack(pady=5)

        # Attach answer image
        tk.Button(
            create_frame,
            text="Attach Answer Image",
            font=("Helvetica", 20),
            command=self.select_answer_image
        ).pack(pady=5)

        # Ctrl+Backspace
        self.question_entry.bind("<Control-BackSpace>", self.ctrl_backspace_handler)
        self.answer_entry.bind("<Control-BackSpace>", self.ctrl_backspace_handler)

        tk.Button(
            create_frame,
            text="Save Flashcard",
            font=("Helvetica", 20),
            command=self.save_new_flashcard
        ).pack(pady=10)

    def on_manage_course_selected(self, event=None):
        """When user selects a course in the 'manage' dropdown."""
        selected_course = self.manage_course_var.get()
        if selected_course in self.courses:
            self.current_course = selected_course
        else:
            self.current_course = None

    # ================================================================
    # Build Tab 2: Study Flashcards
    # ================================================================
    def build_study_tab(self):
        tab = self.tab_study
        tab.config(width=900, height=550)

        # -- Top bar: select course to study --
        study_top_frame = tk.Frame(tab, bg="#F5F5F5")
        study_top_frame.pack(side="top", fill="x", padx=10, pady=(10, 0))

        tk.Label(
            study_top_frame,
            text="Select course to study:",
            font=("Helvetica", 20),
            bg="#F5F5F5"
        ).pack(side="left", padx=(0, 10))

        self.study_course_var = tk.StringVar()
        self.study_course_dropdown = ttk.Combobox(
            study_top_frame,
            textvariable=self.study_course_var,
            state="readonly",
            font=("Helvetica", 20)
        )
        self.study_course_dropdown.pack(side="left")
        self.update_course_dropdown_study()
        self.study_course_dropdown.bind("<<ComboboxSelected>>", self.on_study_course_selected)

        # -- Main study area --
        study_main_frame = tk.Frame(tab, bg="#FFFFFF", bd=2, relief="groove")
        study_main_frame.pack(side="top", fill="both", expand=True, padx=10, pady=10)

        # Question text
        self.question_label_study = tk.Label(
            study_main_frame,
            text="(No course selected)",
            font=("Helvetica", 20, "bold"),
            wraplength=600,
            bg="#FFFFFF",
            fg="#333"
        )
        self.question_label_study.pack(pady=(10, 0))

        # Counter label
        self.counter_label_study = tk.Label(
            study_main_frame,
            text="",
            font=("Helvetica", 20),
            bg="#FFFFFF",
            fg="#333"
        )
        self.counter_label_study.pack(pady=(0,10))

        # Question Image (below question text)
        self.question_img_label = tk.Label(study_main_frame, bg="#FFFFFF")
        self.question_img_label.pack(pady=5)

        # Answer area
        answer_frame = tk.Frame(study_main_frame, bg="#FFFFFF")
        answer_frame.pack(fill="both", expand=True, pady=5)

        self.answer_scrollbar = tk.Scrollbar(answer_frame, orient="vertical")
        self.answer_scrollbar.pack(side="right", fill="y")

        # -- The key change: height=10 --
        self.answer_text_study = tk.Text(
            answer_frame,
            font=("Helvetica", 20),
            wrap="word",
            yscrollcommand=self.answer_scrollbar.set,
            bg="#FFFFFF",
            fg="#333",
            height=10,  # Increased from 5 to 10
            width=40
        )
        self.answer_text_study.pack(side="left", fill="both", expand=True)

        self.answer_scrollbar.config(command=self.answer_text_study.yview)
        self.answer_text_study.config(state="disabled")

        # Answer Image (below the answer text)
        self.answer_img_label = tk.Label(answer_frame, bg="#FFFFFF")
        self.answer_img_label.pack(pady=(5, 0))

        # Bottom buttons
        study_button_frame = tk.Frame(study_main_frame, bg="#FFFFFF")
        study_button_frame.pack(pady=5)

        tk.Button(
            study_button_frame,
            text="Show Answer",
            font=("Helvetica", 20),
            command=self.show_answer
        ).pack(side="left", padx=5)

        tk.Button(
            study_button_frame,
            text="Next Card",
            font=("Helvetica", 20),
            command=self.next_card
        ).pack(side="left", padx=5)

        tk.Button(
            study_button_frame,
            text="Delete Card",
            font=("Helvetica", 20),
            command=self.delete_current_flashcard
        ).pack(side="left", padx=5)

        tk.Button(
            study_button_frame,
            text="Edit Card",
            font=("Helvetica", 20),
            command=self.edit_current_flashcard
        ).pack(side="left", padx=5)

    def on_study_course_selected(self, event=None):
        """When user picks a course to study in Tab 2."""
        selected_course = self.study_course_var.get()
        if selected_course in self.courses:
            self.current_course = selected_course
            self.question_label_study.config(text="Ready to study!")
            self.clear_answer_display()
            self.question_img_label.config(image="", text="")
            self.shuffle_bags[selected_course] = []
            self.current_deck_count = 0
            self.current_deck_seen = 0
            self.counter_label_study.config(text="")
            self.current_flashcard_index = None
        else:
            self.current_course = None
            self.question_label_study.config(text="(No course selected)")
            self.clear_answer_display()
            self.question_img_label.config(image="", text="")
            self.counter_label_study.config(text="")
            self.current_flashcard_index = None

    # ================================================================
    # Data: Loading & Saving
    # ================================================================
    def load_courses(self):
        if os.path.exists(FLASHCARDS_FILE):
            with open(FLASHCARDS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        return {}

    def save_courses_to_disk(self):
        """This function remains, but the button is disabled."""
        with open(FLASHCARDS_FILE, "w", encoding="utf-8") as f:
            json.dump(self.courses, f, indent=4)
        # messagebox.showinfo("Success", "All courses saved to disk.")

    # ================================================================
    # Updating ComboBoxes
    # ================================================================
    def update_course_dropdown(self):
        """Refresh the 'manage' dropdown in Tab 1 with current courses."""
        course_names = list(self.courses.keys())
        self.manage_course_dropdown["values"] = course_names
        if self.current_course in course_names:
            self.manage_course_var.set(self.current_course)
        else:
            self.manage_course_var.set("")

    def update_course_dropdown_study(self):
        """Refresh the 'study' dropdown in Tab 2 with current courses."""
        course_names = list(self.courses.keys())
        self.study_course_dropdown["values"] = course_names
        if self.current_course in course_names:
            self.study_course_var.set(self.current_course)
        else:
            self.study_course_var.set("")

    # ================================================================
    # Creating Flashcards (Tab 1)
    # ================================================================
    def add_new_course(self):
        new_course_name = self.new_course_entry.get().strip()
        if not new_course_name:
            messagebox.showwarning("Warning", "Please enter a valid course name.")
            return

        if new_course_name not in self.courses:
            self.courses[new_course_name] = []
            messagebox.showinfo("Success", f"Course '{new_course_name}' added!")
            self.new_course_entry.delete(0, tk.END)
            self.current_course = new_course_name
        else:
            messagebox.showinfo("Info", f"Course '{new_course_name}' already exists.")
            self.new_course_entry.delete(0, tk.END)

        # Update both dropdowns
        self.update_course_dropdown()
        self.update_course_dropdown_study()
        # Create or reset shuffle bag
        self.shuffle_bags[new_course_name] = []

        self.save_courses_to_disk()

    def select_question_image(self):
        file_path = filedialog.askopenfilename(
            title="Select Question Image",
            filetypes=[("Image Files", "*.png;*.jpg;*.jpeg;*.gif;*.bmp")]
        )
        if file_path:
            self.new_question_img_path = file_path
            messagebox.showinfo("Image Selected", f"Question image attached:\n{file_path}")

    def select_answer_image(self):
        file_path = filedialog.askopenfilename(
            title="Select Answer Image",
            filetypes=[("Image Files", "*.png;*.jpg;*.jpeg;*.gif;*.bmp")]
        )
        if file_path:
            self.new_answer_img_path = file_path
            messagebox.showinfo("Image Selected", f"Answer image attached:\n{file_path}")

    def save_new_flashcard(self):
        """Save a newly created flashcard to the chosen course."""
        if not self.current_course:
            messagebox.showwarning("Warning", "Please select a course first.")
            return

        question_text = self.question_entry.get("1.0", tk.END).strip()
        answer_text = self.answer_entry.get("1.0", tk.END).strip()

        if not question_text and not answer_text and not self.new_question_img_path and not self.new_answer_img_path:
            messagebox.showwarning("Warning", "Please enter a question/answer or attach an image.")
            return

        new_flashcard = {
            "question": question_text,
            "answer": answer_text,
            "question_img": self.new_question_img_path if self.new_question_img_path else None,
            "answer_img": self.new_answer_img_path if self.new_answer_img_path else None
        }
        self.courses[self.current_course].append(new_flashcard)

        # Clear fields
        self.question_entry.delete("1.0", tk.END)
        self.answer_entry.delete("1.0", tk.END)
        self.new_question_img_path = None
        self.new_answer_img_path = None

        # Reset the shuffle bag
        self.shuffle_bags[self.current_course] = []

        # Save
        self.save_courses_to_disk()
        messagebox.showinfo("Success", f"Flashcard saved to course '{self.current_course}'!")

    # ================================================================
    # Studying (Tab 2) with INDEX-based approach
    # ================================================================
    def next_card(self):
        if not self.current_course or self.current_course not in self.courses:
            messagebox.showwarning("Warning", "Please select a valid course in the Study tab.")
            return

        flashcards = self.courses[self.current_course]
        if not flashcards:
            self.question_label_study.config(text="No flashcards in this course yet.")
            self.clear_answer_display()
            self.counter_label_study.config(text="")
            self.question_img_label.config(image="", text="")
            self.current_flashcard_index = None
            return

        # Build or reuse a shuffle bag of *indices*
        if self.current_course not in self.shuffle_bags:
            self.shuffle_bags[self.current_course] = []

        if len(self.shuffle_bags[self.current_course]) == 0:
            new_bag = list(range(len(flashcards)))  # store indices (0..N-1)
            random.shuffle(new_bag)
            self.shuffle_bags[self.current_course] = new_bag
            self.current_deck_count = len(new_bag)
            self.current_deck_seen = 0

        # Pop an index from the bag
        self.current_flashcard_index = self.shuffle_bags[self.current_course].pop()
        self.current_deck_seen += 1

        # Retrieve the flashcard dict
        card_data = flashcards[self.current_flashcard_index]

        # Display question text
        self.question_label_study.config(
            text=card_data.get("question") or "[No question text]"
        )
        # Display question image (below text)
        self.show_question_image(card_data.get("question_img"))

        # Clear answer
        self.clear_answer_display()

        # Update counter
        self.counter_label_study.config(
            text=f"Card {self.current_deck_seen} of {self.current_deck_count}"
        )

    def show_answer(self):
        if self.current_flashcard_index is None:
            messagebox.showinfo("Info", "No flashcard is selected. Click 'Next Card' first.")
            return

        flashcards = self.courses.get(self.current_course, [])
        if not flashcards or self.current_flashcard_index >= len(flashcards):
            messagebox.showinfo("Info", "No valid flashcard to show.")
            return

        card_data = flashcards[self.current_flashcard_index]
        answer_text = card_data.get("answer") or "[No answer text]"

        self.answer_text_study.config(state="normal")
        self.answer_text_study.delete("1.0", tk.END)
        self.answer_text_study.insert(tk.END, answer_text)
        self.answer_text_study.config(state="disabled")

        # Display answer image
        answer_img = card_data.get("answer_img")
        self.show_answer_image(answer_img)

    def delete_current_flashcard(self):
        if not self.current_course or self.current_course not in self.courses:
            messagebox.showwarning("Warning", "Please select a valid course.")
            return
        if self.current_flashcard_index is None:
            messagebox.showinfo("Info", "No flashcard is selected.")
            return

        flashcards = self.courses[self.current_course]
        # Check that index is valid
        if self.current_flashcard_index < 0 or self.current_flashcard_index >= len(flashcards):
            messagebox.showinfo("Info", "No valid flashcard is selected.")
            return

        # Remove that flashcard
        flashcards.pop(self.current_flashcard_index)
        self.save_courses_to_disk()

        self.shuffle_bags[self.current_course] = []
        self.current_flashcard_index = None

        # Reset
        self.question_label_study.config(text="Flashcard deleted. Click 'Next Card' to continue.")
        self.clear_answer_display()
        self.question_img_label.config(image="", text="")
        self.counter_label_study.config(text="")

        messagebox.showinfo("Success", "The current flashcard has been deleted.")

    def edit_current_flashcard(self):
        if not self.current_course or self.current_course not in self.courses:
            messagebox.showinfo("Info", "No course selected.")
            return
        if self.current_flashcard_index is None:
            messagebox.showinfo("Info", "No flashcard is selected. Click 'Next Card' first.")
            return

        flashcards = self.courses[self.current_course]
        if self.current_flashcard_index < 0 or self.current_flashcard_index >= len(flashcards):
            messagebox.showinfo("Info", "No valid flashcard selected.")
            return

        # This is the flashcard dictionary
        card_data = flashcards[self.current_flashcard_index]

        # Popup for editing
        edit_window = tk.Toplevel(self.master)
        edit_window.title("Edit Flashcard")
        edit_window.geometry("500x400")
        edit_window.config(bg="#F5F5F5")

        tk.Label(edit_window, text="Edit Question:", bg="#F5F5F5", font=("Helvetica", 20)).pack(pady=(10,0))
        edit_question_text = tk.Text(edit_window, height=3, width=40, wrap="word", font=("Helvetica", 20))
        edit_question_text.pack(pady=5)
        edit_question_text.insert(tk.END, card_data.get("question", ""))

        # Let user change question image
        new_qimg = [card_data.get("question_img", None)]
        def change_qimg():
            file_path = filedialog.askopenfilename(
                title="Select New Question Image",
                filetypes=[("Image Files", "*.png;*.jpg;*.jpeg;*.gif;*.bmp")]
            )
            if file_path:
                new_qimg[0] = file_path
                messagebox.showinfo("Image Attached", f"New question image:\n{file_path}")
        tk.Button(edit_window, text="Change Question Image", font=("Helvetica", 20), command=change_qimg).pack(pady=2)

        tk.Label(edit_window, text="Edit Answer:", bg="#F5F5F5", font=("Helvetica", 20)).pack(pady=(10,0))
        edit_answer_text = tk.Text(edit_window, height=3, width=40, wrap="word", font=("Helvetica", 20))
        edit_answer_text.pack(pady=5)
        edit_answer_text.insert(tk.END, card_data.get("answer", ""))

        new_aimg = [card_data.get("answer_img", None)]
        def change_aimg():
            file_path = filedialog.askopenfilename(
                title="Select New Answer Image",
                filetypes=[("Image Files", "*.png;*.jpg;*.jpeg;*.gif;*.bmp")]
            )
            if file_path:
                new_aimg[0] = file_path
                messagebox.showinfo("Image Attached", f"New answer image:\n{file_path}")
        tk.Button(edit_window, text="Change Answer Image", font=("Helvetica", 20), command=change_aimg).pack(pady=2)

        edit_question_text.bind("<Control-BackSpace>", self.ctrl_backspace_handler)
        edit_answer_text.bind("<Control-BackSpace>", self.ctrl_backspace_handler)

        def save_changes():
            updated_question = edit_question_text.get("1.0", tk.END).strip()
            updated_answer = edit_answer_text.get("1.0", tk.END).strip()

            # Both images stored in new_qimg[0], new_aimg[0]
            if not (updated_question or updated_answer or new_qimg[0] or new_aimg[0]):
                messagebox.showwarning("Warning", "Flashcard can't be entirely empty.")
                return

            card_data["question"] = updated_question
            card_data["answer"] = updated_answer
            card_data["question_img"] = new_qimg[0]
            card_data["answer_img"]   = new_aimg[0]

            self.save_courses_to_disk()
            # Reset shuffle so next_card can reflect changes
            self.shuffle_bags[self.current_course] = []

            # If it's the current card, update UI
            self.question_label_study.config(text=updated_question or "[No question text]")
            self.show_question_image(new_qimg[0])
            self.clear_answer_display()

            messagebox.showinfo("Success", "Flashcard updated!")
            edit_window.destroy()

        tk.Button(edit_window, text="Save Changes", font=("Helvetica", 20), command=save_changes).pack(pady=15)

    # ================================================================
    # Utility / Image Display
    # ================================================================
    def show_question_image(self, path):
        """Display question image below the question text."""
        if path and os.path.exists(path):
            try:
                img = Image.open(path)
                # Use Resampling.LANCZOS if available (Pillow>=9.1)
                img.thumbnail((400, 400), Resampling.LANCZOS)
                self.question_img_obj = ImageTk.PhotoImage(img)
                self.question_img_label.config(image=self.question_img_obj, text="")
            except Exception:
                self.question_img_label.config(image="", text="(Error loading image)")
        else:
            self.question_img_label.config(image="", text="")
            self.question_img_obj = None

    def show_answer_image(self, path):
        """Display answer image below the answer text."""
        if path and os.path.exists(path):
            try:
                img = Image.open(path)
                img.thumbnail((400, 400), Resampling.LANCZOS)
                self.answer_img_obj = ImageTk.PhotoImage(img)
                self.answer_img_label.config(image=self.answer_img_obj, text="")
            except Exception:
                self.answer_img_label.config(image="", text="(Error loading image)")
        else:
            self.answer_img_label.config(image="", text="")
            self.answer_img_obj = None

    def clear_answer_display(self):
        """Clears both the answer text and the answer image."""
        self.answer_text_study.config(state="normal")
        self.answer_text_study.delete("1.0", tk.END)
        self.answer_text_study.config(state="disabled")
        self.answer_img_label.config(image="", text="")
        self.answer_img_obj = None

    def ctrl_backspace_handler(self, event):
        """Implements typical Ctrl+Backspace word deletion in a Text widget."""
        widget = event.widget
        insert_pos = widget.index(tk.INSERT)
        text_before_cursor = widget.get("1.0", insert_pos)
        if not text_before_cursor.strip():
            return "break"
        backward_index = len(text_before_cursor) - 1
        while backward_index >= 0 and not text_before_cursor[backward_index].isspace():
            backward_index -= 1
        delete_start = f"{float(widget.index('1.0')) + (backward_index+1)/1000}"
        widget.delete(delete_start, insert_pos)
        return "break"

# ================================================================
# Main
# ================================================================
if __name__ == "__main__":
    root = tk.Tk()
    app = FlashcardApp(root)
    root.mainloop()
