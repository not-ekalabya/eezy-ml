# Design System Specification: High-End Cloud Console

## 1. Overview & Creative North Star
**Creative North Star: "The Monolith"**
This design system moves away from the cluttered, dashboard-heavy aesthetics of legacy cloud platforms. It is built on the philosophy of **Architectural Brutalism meets Soft Minimalism.** By stripping away the noise of vibrant status colors and heavy borders, we create a "Monolith" experience—an interface that feels carved from a single block of obsidian, where importance is defined by light, typography, and physical depth rather than decoration.

The system breaks the "standard template" look through intentional asymmetry: using expansive white space (`spacing.24`) to offset dense data clusters, ensuring the console feels like a premium editorial tool rather than a spreadsheet.

---

## 2. Colors & Surface Logic
The palette is a strict monochromatic study. Depth is not a decoration; it is information.

### The "No-Line" Rule
Traditional 1px solid borders are strictly prohibited for sectioning. Structural separation must be achieved through **Background Color Shifts**. 
*   *Example:* A navigation sidebar should be `surface_container_low` (#1C1B1B) sitting against a `surface` (#131313) main stage.

### Surface Hierarchy & Nesting
Treat the UI as a series of physical layers. Use the following tiers to define nesting:
1.  **Base Layer:** `surface` (#131313)
2.  **Sectioning:** `surface_container_low` (#1C1B1B) for secondary regions.
3.  **Interactive Cards:** `surface_container` (#201F1F) for standard elements.
4.  **Floating Modals/Popovers:** `surface_bright` (#3A3939) to draw the eye forward.

### The Glass & Gradient Rule
To prevent the UI from feeling "flat" or "dead," primary actions and hero states should utilize subtle tonal transitions.
*   **Signature CTA:** A linear gradient from `primary` (#FFFFFF) to `primary_container` (#D4D4D4) at a 45-degree angle.
*   **Overlays:** Use `surface_container_highest` (#353534) at 80% opacity with a `20px` backdrop-blur to create a "frosted obsidian" effect for dropdowns and tooltips.

---

## 3. Typography
We utilize **Inter** as our typographic anchor. It is modern, neutral, and highly legible at the small scales required for cloud infrastructure data.

*   **Display (The Statement):** `display-lg` (3.5rem) should be used sparingly for empty states or hero metrics. Use `on_surface` (#E5E2E1) with tight letter-spacing (-0.02em).
*   **Headline (The Narrative):** `headline-sm` (1.5rem) defines major console modules. It provides the authoritative "editorial" voice.
*   **Body (The Utility):** `body-md` (0.875rem) is the workhorse. Use `on_surface_variant` (#C6C6C6) for secondary descriptions to maintain a clear visual hierarchy against white primary text.
*   **Labels (The Metadata):** `label-sm` (0.6875rem) in All-Caps with +0.05em tracking for technical IDs and system tags.

---

## 4. Elevation & Depth
In this design system, elevation is conveyed through **Tonal Layering**, not shadows.

*   **The Layering Principle:** Place a `surface_container_lowest` (#0E0E0E) card inside a `surface_container` (#201F1F) section to create a "recessed" look for data logs.
*   **Ambient Shadows:** If a floating element (like a context menu) requires a shadow, use a diffuse spread: `0px 20px 40px rgba(0,0,0,0.4)`. Never use harsh, dark drop shadows.
*   **The "Ghost Border" Fallback:** Where accessibility requires a container edge, use a Ghost Border: `outline_variant` (#474747) at **15% opacity**. This provides a hint of a boundary without breaking the monochromatic flow.

---

## 5. Components

### Buttons
*   **Primary:** Background `primary` (#FFFFFF), Text `on_primary` (#1A1C1C). **State:** Hover increases brightness slightly; Active scales to 98%.
*   **Secondary:** Background `none`, Border `Ghost Border`, Text `on_surface`. 
*   **Tertiary (Ghost):** Background `none`, Text `on_surface_variant`. 

### Input Fields
*   **Default:** `surface_container_highest` (#353534) background, no border, `sm` (0.125rem) radius.
*   **Focus State:** A 1px `primary` (#FFFFFF) bottom-border only. This maintains the "architectural" feel.

### Cards & Lists
*   **The "No-Divider" Rule:** Forbid 1px dividers between list items. Instead, use `spacing.2` (0.4rem) of vertical white space and a subtle background change (`surface_container_low`) on hover to define the row.

### Cloud-Specific Components
*   **Status Indicators:** Since we avoid vibrant colors, "Active" states are indicated by a `primary` (#FFFFFF) pulse, and "Error" states use the `error` (#FFB4AB) token only for the icon, keeping the surrounding container neutral.
*   **Resource Bars:** Use `primary_fixed_dim` (#454747) for the track and `primary` (#FFFFFF) for the fill.

---

## 6. Do's and Don'ts

### Do:
*   **Do** use `spacing.16` or `20` to separate major functional blocks. Let the interface breathe.
*   **Do** use `roundedness.md` (0.375rem) for most interactive elements to soften the brutalist edges.
*   **Do** prioritize `on_surface_variant` for all non-essential text to ensure the `primary` white text acts as a beacon for the user's eyes.

### Don't:
*   **Don't** use pure #000000 for backgrounds. It kills the ability to create "recessed" depth. Use `surface_container_lowest` (#0E0E0E).
*   **Don't** use more than one `primary` action per view. The high-contrast white button should be the unmistakable "Next Step."
*   **Don't** use standard blue for links. Links should be underlined `on_surface` text.
