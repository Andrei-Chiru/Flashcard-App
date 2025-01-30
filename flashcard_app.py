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
        self.master.title("Flashcard Study App - Two Tabs (Multiple Images)")
        self.master.geometry("900x550")
        self.master.config(bg="#F5F5F5")

        # ------------------------------------------------
        # Internal Data
        # ------------------------------------------------
        self.courses = self.load_courses()  # { courseName: [ { "question":..., "answer":..., "question_imgs":[], "answer_imgs":[]} ] }
        self.current_course = None

        # Store the current flashcard's index in self.courses[self.current_course].
        self.current_flashcard_index = None

        # For random deck usage without repeats:
        self.shuffle_bags = {}
        self.current_deck_count = 0
        self.current_deck_seen = 0

        # For storing new images in the "create" tab
        self.new_question_img_paths = []
        self.new_answer_img_paths = []
        # We'll keep references to the preview image objects to avoid GC
        self.new_question_img_objs = []
        self.new_answer_img_objs = []

        # We'll keep references to displayed images in the study tab
        self.question_img_objs_study = []
        self.answer_img_objs_study = []

        # ------------------------------------------------
        # Build the UI (Notebook with 2 tabs)
        # ------------------------------------------------
        self.notebook = ttk.Notebook(self.master)
        self.notebook.pack(fill="both", expand=True)

        self.tab_create_manage = ttk.Frame(self.notebook)
        self.tab_study = ttk.Frame(self.notebook)

        self.notebook.add(self.tab_create_manage, text="Create & Manage")
        self.notebook.add(self.tab_study, text="Study")

        self.build_create_manage_tab()
        self.build_study_tab()

    # ================================================================
    # Build Tab 1: Create & Manage
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

        # (Optional) Disabled 'Save All Courses' button code removed for brevity.

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

        # Frame to preview question images
        self.question_preview_frame = tk.Frame(create_frame, bg="#FFFFFF")
        self.question_preview_frame.pack(pady=5)

        tk.Button(
            create_frame,
            text="Attach Question Image",
            font=("Helvetica", 20),
            command=self.select_question_image
        ).pack(pady=5)

        tk.Label(create_frame, text="Answer:", bg="#FFFFFF", font=("Helvetica", 20)).pack()
        self.answer_entry = tk.Text(create_frame, height=3, width=35, wrap="word", font=("Helvetica", 20))
        self.answer_entry.pack(pady=5)

        # Frame to preview answer images
        self.answer_preview_frame = tk.Frame(create_frame, bg="#FFFFFF")
        self.answer_preview_frame.pack(pady=5)

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
        selected_course = self.manage_course_var.get()
        if selected_course in self.courses:
            self.current_course = selected_course
        else:
            self.current_course = None

    # ================================================================
    # Build Tab 2: Study
    # ================================================================
    def build_study_tab(self):
        tab = self.tab_study
        tab.config(width=900, height=550)

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

        study_main_frame = tk.Frame(tab, bg="#FFFFFF", bd=2, relief="groove")
        study_main_frame.pack(side="top", fill="both", expand=True, padx=10, pady=10)

        self.question_label_study = tk.Label(
            study_main_frame,
            text="(No course selected)",
            font=("Helvetica", 20, "bold"),
            wraplength=600,
            bg="#FFFFFF",
            fg="#333"
        )
        self.question_label_study.pack(pady=(10, 0))

        self.counter_label_study = tk.Label(
            study_main_frame,
            text="",
            font=("Helvetica", 20),
            bg="#FFFFFF",
            fg="#333"
        )
        self.counter_label_study.pack(pady=(0,10))

        # Frame for question images
        self.question_images_frame_study = tk.Frame(study_main_frame, bg="#FFFFFF")
        self.question_images_frame_study.pack(pady=5)

        answer_frame = tk.Frame(study_main_frame, bg="#FFFFFF")
        answer_frame.pack(fill="both", expand=True, pady=5)

        self.answer_scrollbar = tk.Scrollbar(answer_frame, orient="vertical")
        self.answer_scrollbar.pack(side="right", fill="y")

        self.answer_text_study = tk.Text(
            answer_frame,
            font=("Helvetica", 20),
            wrap="word",
            yscrollcommand=self.answer_scrollbar.set,
            bg="#FFFFFF",
            fg="#333",
            height=10,
            width=40
        )
        self.answer_text_study.pack(side="left", fill="both", expand=True)
        self.answer_scrollbar.config(command=self.answer_text_study.yview)
        self.answer_text_study.config(state="disabled")

        # Frame for answer images
        self.answer_images_frame_study = tk.Frame(answer_frame, bg="#FFFFFF")
        self.answer_images_frame_study.pack(side="left", fill="both", expand=True, pady=5)

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
        selected_course = self.study_course_var.get()
        if selected_course in self.courses:
            self.current_course = selected_course
            self.question_label_study.config(text="Ready to study!")
            self.clear_answer_display()
            self.clear_question_images_study()
            self.shuffle_bags[selected_course] = []
            self.current_deck_count = 0
            self.current_deck_seen = 0
            self.counter_label_study.config(text="")
            self.current_flashcard_index = None
        else:
            self.current_course = None
            self.question_label_study.config(text="(No course selected)")
            self.clear_answer_display()
            self.clear_question_images_study()
            self.counter_label_study.config(text="")
            self.current_flashcard_index = None

    # ================================================================
    # Data Loading / Saving
    # ================================================================
    def load_courses(self):
        if os.path.exists(FLASHCARDS_FILE):
            with open(FLASHCARDS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        return {}

    def save_courses_to_disk(self):
        """No pop-up message here."""
        with open(FLASHCARDS_FILE, "w", encoding="utf-8") as f:
            json.dump(self.courses, f, indent=4)

    # ================================================================
    # Updating ComboBoxes
    # ================================================================
    def update_course_dropdown(self):
        course_names = list(self.courses.keys())
        self.manage_course_dropdown["values"] = course_names
        if self.current_course in course_names:
            self.manage_course_var.set(self.current_course)
        else:
            self.manage_course_var.set("")

    def update_course_dropdown_study(self):
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

        self.update_course_dropdown()
        self.update_course_dropdown_study()
        self.shuffle_bags[new_course_name] = []

        self.save_courses_to_disk()

    def select_question_image(self):
        file_path = filedialog.askopenfilename(
            title="Select Question Image",
            filetypes=[("Image Files", "*.png;*.jpg;*.jpeg;*.gif;*.bmp")]
        )
        if file_path:
            self.new_question_img_paths.append(file_path)
            self.show_question_image_preview(file_path)

    def select_answer_image(self):
        file_path = filedialog.askopenfilename(
            title="Select Answer Image",
            filetypes=[("Image Files", "*.png;*.jpg;*.jpeg;*.gif;*.bmp")]
        )
        if file_path:
            self.new_answer_img_paths.append(file_path)
            self.show_answer_image_preview(file_path)

    def show_question_image_preview(self, path):
        """Display a small thumbnail in the question_preview_frame."""
        try:
            img = Image.open(path)
            img.thumbnail((100, 100), Resampling.LANCZOS)
            img_obj = ImageTk.PhotoImage(img)
            self.new_question_img_objs.append(img_obj)
            lbl = tk.Label(self.question_preview_frame, image=img_obj, bg="#FFFFFF")
            lbl.pack(side="top", anchor="center", pady=2)
        except:
            pass

    def show_answer_image_preview(self, path):
        """Display a small thumbnail in the answer_preview_frame."""
        try:
            img = Image.open(path)
            img.thumbnail((100, 100), Resampling.LANCZOS)
            img_obj = ImageTk.PhotoImage(img)
            self.new_answer_img_objs.append(img_obj)
            lbl = tk.Label(self.answer_preview_frame, image=img_obj, bg="#FFFFFF")
            lbl.pack(side="top", anchor="center", pady=2)
        except:
            pass

    def save_new_flashcard(self):
        if not self.current_course:
            messagebox.showwarning("Warning", "Please select a course first.")
            return

        question_text = self.question_entry.get("1.0", tk.END).strip()
        answer_text = self.answer_entry.get("1.0", tk.END).strip()

        if not question_text and not answer_text and not self.new_question_img_paths and not self.new_answer_img_paths:
            messagebox.showwarning("Warning", "Please enter text or attach images.")
            return

        new_flashcard = {
            "question": question_text,
            "answer": answer_text,
            "question_imgs": list(self.new_question_img_paths),
            "answer_imgs": list(self.new_answer_img_paths)
        }
        self.courses[self.current_course].append(new_flashcard)

        # Clear text fields
        self.question_entry.delete("1.0", tk.END)
        self.answer_entry.delete("1.0", tk.END)

        # Clear image lists
        self.new_question_img_paths.clear()
        self.new_answer_img_paths.clear()

        # Clear preview frames
        for widget in self.question_preview_frame.winfo_children():
            widget.destroy()
        for widget in self.answer_preview_frame.winfo_children():
            widget.destroy()

        self.new_question_img_objs.clear()
        self.new_answer_img_objs.clear()

        # Reset shuffle bag
        self.shuffle_bags[self.current_course] = []

        self.save_courses_to_disk()
        messagebox.showinfo("Success", f"Flashcard saved to course '{self.current_course}'!")

    # ================================================================
    # Studying with INDEX-based approach
    # ================================================================
    def next_card(self):
        if not self.current_course or self.current_course not in self.courses:
            messagebox.showwarning("Warning", "Please select a valid course in the Study tab.")
            return

        flashcards = self.courses[self.current_course]
        if not flashcards:
            self.question_label_study.config(text="No flashcards in this course yet.")
            self.clear_answer_display()
            self.clear_question_images_study()
            self.counter_label_study.config(text="")
            self.current_flashcard_index = None
            return

        # Build or reuse a shuffle bag of indices
        if self.current_course not in self.shuffle_bags:
            self.shuffle_bags[self.current_course] = []

        if len(self.shuffle_bags[self.current_course]) == 0:
            new_bag = list(range(len(flashcards)))
            random.shuffle(new_bag)
            self.shuffle_bags[self.current_course] = new_bag
            self.current_deck_count = len(new_bag)
            self.current_deck_seen = 0

        self.current_flashcard_index = self.shuffle_bags[self.current_course].pop()
        self.current_deck_seen += 1

        card_data = flashcards[self.current_flashcard_index]

        # Show question text
        self.question_label_study.config(
            text=card_data.get("question") or "[No question text]"
        )
        # Show question images
        self.display_question_images_study(card_data.get("question_imgs", []))

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

        # Insert text (do NOT remove it afterwards!)
        self.answer_text_study.config(state="normal")
        self.answer_text_study.delete("1.0", tk.END)
        self.answer_text_study.insert(tk.END, answer_text)
        self.answer_text_study.config(state="disabled")

        # Display answer images
        # => Note: we do NOT call clear_answer_display again here.
        self.display_answer_images_study(card_data.get("answer_imgs", []))

    def delete_current_flashcard(self):
        if not self.current_course or self.current_course not in self.courses:
            messagebox.showwarning("Warning", "Please select a valid course.")
            return
        if self.current_flashcard_index is None:
            messagebox.showinfo("Info", "No flashcard is selected.")
            return

        flashcards = self.courses[self.current_course]
        if self.current_flashcard_index < 0 or self.current_flashcard_index >= len(flashcards):
            messagebox.showinfo("Info", "No valid flashcard is selected.")
            return

        flashcards.pop(self.current_flashcard_index)
        self.save_courses_to_disk()

        self.shuffle_bags[self.current_course] = []
        self.current_flashcard_index = None

        self.question_label_study.config(text="Flashcard deleted. Click 'Next Card' to continue.")
        self.clear_answer_display()
        self.clear_question_images_study()
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

        card_data = flashcards[self.current_flashcard_index]

        # Popup
        edit_window = tk.Toplevel(self.master)
        edit_window.title("Edit Flashcard")
        edit_window.geometry("500x400")
        edit_window.config(bg="#F5F5F5")

        tk.Label(edit_window, text="Edit Question:", bg="#F5F5F5", font=("Helvetica", 20)).pack(pady=(10,0))
        edit_question_text = tk.Text(edit_window, height=3, width=40, wrap="word", font=("Helvetica", 20))
        edit_question_text.pack(pady=5)
        edit_question_text.insert(tk.END, card_data.get("question", ""))

        question_imgs = list(card_data.get("question_imgs", []))
        def add_qimg():
            file_path = filedialog.askopenfilename(
                title="Select New Question Image",
                filetypes=[("Image Files", "*.png;*.jpg;*.jpeg;*.gif;*.bmp")]
            )
            if file_path:
                question_imgs.append(file_path)
                messagebox.showinfo("Image Attached", f"New question image:\n{file_path}")

        tk.Button(edit_window, text="Add Question Image", font=("Helvetica", 20), command=add_qimg).pack(pady=2)

        tk.Label(edit_window, text="Edit Answer:", bg="#F5F5F5", font=("Helvetica", 20)).pack(pady=(10,0))
        edit_answer_text = tk.Text(edit_window, height=3, width=40, wrap="word", font=("Helvetica", 20))
        edit_answer_text.pack(pady=5)
        edit_answer_text.insert(tk.END, card_data.get("answer", ""))

        answer_imgs = list(card_data.get("answer_imgs", []))
        def add_aimg():
            file_path = filedialog.askopenfilename(
                title="Select New Answer Image",
                filetypes=[("Image Files", "*.png;*.jpg;*.jpeg;*.gif;*.bmp")]
            )
            if file_path:
                answer_imgs.append(file_path)
                messagebox.showinfo("Image Attached", f"New answer image:\n{file_path}")

        tk.Button(edit_window, text="Add Answer Image", font=("Helvetica", 20), command=add_aimg).pack(pady=2)

        edit_question_text.bind("<Control-BackSpace>", self.ctrl_backspace_handler)
        edit_answer_text.bind("<Control-BackSpace>", self.ctrl_backspace_handler)

        def save_changes():
            updated_question = edit_question_text.get("1.0", tk.END).strip()
            updated_answer = edit_answer_text.get("1.0", tk.END).strip()

            if not (updated_question or updated_answer or question_imgs or answer_imgs):
                messagebox.showwarning("Warning", "Flashcard can't be entirely empty.")
                return

            card_data["question"] = updated_question
            card_data["answer"] = updated_answer
            card_data["question_imgs"] = question_imgs
            card_data["answer_imgs"]   = answer_imgs

            self.save_courses_to_disk()
            self.shuffle_bags[self.current_course] = []

            # Update the UI if it's the current card
            self.question_label_study.config(text=updated_question or "[No question text]")
            self.display_question_images_study(question_imgs)
            self.clear_answer_display()

            messagebox.showinfo("Success", "Flashcard updated!")
            edit_window.destroy()

        tk.Button(edit_window, text="Save Changes", font=("Helvetica", 20), command=save_changes).pack(pady=15)

    # ================================================================
    # Utility: Study Tab Image Display
    # ================================================================
    def clear_question_images_study(self):
        """Remove all question image labels from the study frame."""
        for child in self.question_images_frame_study.winfo_children():
            child.destroy()
        self.question_img_objs_study.clear()

    def display_question_images_study(self, paths):
        """Display question images in a vertical column, centered."""
        # 1) Clear old question images
        self.clear_question_images_study()
        # 2) Insert new images
        for p in paths:
            if os.path.exists(p):
                try:
                    img = Image.open(p)
                    img.thumbnail((400, 400), Resampling.LANCZOS)
                    img_obj = ImageTk.PhotoImage(img)
                    self.question_img_objs_study.append(img_obj)
                    lbl = tk.Label(self.question_images_frame_study, image=img_obj, bg="#FFFFFF")
                    lbl.pack(side="top", anchor="center", pady=5)
                except:
                    lbl = tk.Label(self.question_images_frame_study, text="(Error loading image)", bg="#FFFFFF")
                    lbl.pack(side="top", anchor="center", pady=5)

    def clear_answer_display(self):
        """
        Clears both the answer text and the *old* answer images.
        We'll call this before showing a *new* card.
        In show_answer(), we do NOT re-clear after inserting text.
        """
        self.answer_text_study.config(state="normal")
        self.answer_text_study.delete("1.0", tk.END)
        self.answer_text_study.config(state="disabled")

        for child in self.answer_images_frame_study.winfo_children():
            child.destroy()
        self.answer_img_objs_study.clear()

    def display_answer_images_study(self, paths):
        """
        Display all answer images in a vertical column, centered.
        Note: We do NOT call clear_answer_display() here,
        so we don't erase the newly inserted text.
        """
        # Clear only old images, not the text
        for child in self.answer_images_frame_study.winfo_children():
            child.destroy()
        self.answer_img_objs_study.clear()

        # Insert new images
        for p in paths:
            if os.path.exists(p):
                try:
                    img = Image.open(p)
                    img.thumbnail((400, 400), Resampling.LANCZOS)
                    img_obj = ImageTk.PhotoImage(img)
                    self.answer_img_objs_study.append(img_obj)
                    lbl = tk.Label(self.answer_images_frame_study, image=img_obj, bg="#FFFFFF")
                    lbl.pack(side="top", anchor="center", pady=5)
                except:
                    lbl = tk.Label(self.answer_images_frame_study, text="(Error loading image)", bg="#FFFFFF")
                    lbl.pack(side="top", anchor="center", pady=5)

    # ================================================================
    # Utility: CTRL+Backspace in a Text widget
    # ================================================================
    def ctrl_backspace_handler(self, event):
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
