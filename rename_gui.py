#!/usr/bin/env python3
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog
import os
import shutil
from app import provider_keywords, purpose_keywords, rename_logic

class RenameApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Document Renamer")
        self.files = []
        self.output_dir = os.path.abspath('processed')
        self.custom_code = tk.StringVar(value='DOC')

        # File selection
        tk.Button(root, text="Select Files", command=self.select_files).pack(pady=5)
        self.files_label = tk.Label(root, text="No files selected.")
        self.files_label.pack()

        # Output directory
        tk.Button(root, text="Select Output Directory", command=self.select_output_dir).pack(pady=5)
        self.output_label = tk.Label(root, text=f"Output: {self.output_dir}")
        self.output_label.pack()

        # Custom code
        tk.Label(root, text="Custom Code (optional):").pack(pady=5)
        tk.Entry(root, textvariable=self.custom_code).pack()

        # Rename button
        tk.Button(root, text="Rename Files", command=self.rename_files).pack(pady=10)

        # Results
        self.results = tk.Text(root, height=12, width=60)
        self.results.pack(pady=5)
        self.results.config(state=tk.DISABLED)

    def select_files(self):
        files = filedialog.askopenfilenames(title="Select files", filetypes=[("Documents", ".pdf .jpg .jpeg .png .tiff .bmp .webp")])
        if files:
            self.files = list(files)
            self.files_label.config(text=f"Selected: {len(self.files)} file(s)")
        else:
            self.files = []
            self.files_label.config(text="No files selected.")

    def select_output_dir(self):
        dir_ = filedialog.askdirectory(title="Select output directory")
        if dir_:
            self.output_dir = dir_
            self.output_label.config(text=f"Output: {self.output_dir}")

    def rename_files(self):
        if not self.files:
            messagebox.showwarning("No files", "Please select files to rename.")
            return
        os.makedirs(self.output_dir, exist_ok=True)
        self.results.config(state=tk.NORMAL)
        self.results.delete(1.0, tk.END)
        for filepath in self.files:
            try:
                new_name, fields = rename_logic(filepath, provider_keywords, purpose_keywords, self.custom_code.get())
                dest_path = os.path.join(self.output_dir, new_name)
                shutil.copy(filepath, dest_path)
                self.results.insert(tk.END, f"{os.path.basename(filepath)} -> {new_name}\n")
                self.results.insert(tk.END, f"  Fields: {fields}\n\n")
            except Exception as e:
                self.results.insert(tk.END, f"[ERROR] {filepath}: {e}\n")
        self.results.config(state=tk.DISABLED)
        messagebox.showinfo("Done", "Renaming complete!")

if __name__ == "__main__":
    root = tk.Tk()
    app = RenameApp(root)
    root.mainloop() 