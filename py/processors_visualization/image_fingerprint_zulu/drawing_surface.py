from PIL import Image, ImageDraw, ImageFont
import colorsys
import math

class DrawingSurface:
    """Drawing surface class - represents a graphics device with model-to-view coordinate conversion"""
    
    def __init__(self, grid_cols: int, grid_rows: int, intracell_cols: int, intracell_rows: int, 
                 legend_rows: int, legend_cols: int, config: dict):
        """Constructor - initializes graphics device and calculates dimensions"""
        self.grid_cols = grid_cols
        self.grid_rows = grid_rows
        self.intracell_cols = intracell_cols
        self.intracell_rows = intracell_rows
        self.legend_rows = legend_rows
        self.legend_cols = legend_cols
        self.config = config
        
        # Calculate font sizes based on datapoint dimensions from config
        self.font_sizes = self._get_font_sizes()
        
        # Use datapoint dimensions from config
        self.datapoint_width = int(self.config["DATAPOINT_WIDTH_PX"])
        self.datapoint_height = int(self.config["DATAPOINT_HEIGHT_PX"])
        
        # Calculate cell dimensions
        self.cell_width = intracell_cols * self.datapoint_width
        self.cell_height = intracell_rows * self.datapoint_height
        
        # Determine layout mode and calculate page counts
        if self.intracell_cols > 1:  # ZICV mode
            self.layout_mode = "zicv"
            max_cells_per_page = self.config["max_hgrid_cells_per_line"]
            self.total_pages = math.ceil(grid_cols / max_cells_per_page)
            self.cells_per_page = min(grid_cols, max_cells_per_page)
            self.orthogonal_cells = grid_rows
        else:  # ZICH mode
            self.layout_mode = "zich"
            max_cells_per_page = self.config["max_vgrid_cells_per_column"]
            self.total_pages = math.ceil(grid_rows / max_cells_per_page)
            self.cells_per_page = min(grid_rows, max_cells_per_page)
            self.orthogonal_cells = grid_cols
        
        # Calculate single page data grid dimensions
        if self.layout_mode == "zicv":
            self.page_data_grid_width = self.cells_per_page * self.cell_width
            self.page_data_grid_height = self.orthogonal_cells * self.cell_height
        else:  # zich
            self.page_data_grid_width = self.orthogonal_cells * self.cell_width
            self.page_data_grid_height = self.cells_per_page * self.cell_height
        
        # Calculate image dimensions using dynamic layout with multiple pages
        grid_page_width_model, grid_page_height_model = self._calculate_grid_page_size()
        
        if self.layout_mode == "zicv":
            # ZICV: Multiple pages stacked vertically
            self.img_width = int((self.config["page_left_padding"] + grid_page_width_model + self.config["page_right_padding"]) * self.datapoint_width)
            
            # Height includes all pages plus outer page margins
            total_height_model = (
                self.config["page_top_padding"] +
                (self.total_pages * grid_page_height_model) +
                0 +  # legend_height = 0
                self.config["page_bottom_padding"]
            )
            self.img_height = int(total_height_model * self.datapoint_height)
            
        else:  # zich
            # ZICH: Multiple pages arranged horizontally
            self.img_height = int((self.config["page_top_padding"] + grid_page_height_model + 0 + self.config["page_bottom_padding"]) * self.datapoint_height)
            
            # Width includes all pages plus outer page margins
            total_width_model = (
                self.config["page_left_padding"] +
                (self.total_pages * grid_page_width_model) +
                self.config["page_right_padding"]
            )
            self.img_width = int(total_width_model * self.datapoint_width)
        
        # Calculate base zone boundaries (for page 0)
        minor_label_width = self.config["vertical_minor_label_strip_width"] if self.intracell_rows > 1 else 0
        minor_label_height = self.config["minor_label_strip_height"] if self.intracell_cols > 1 else 0
        
        self.base_data_zone_x = int((self.config["page_left_padding"] + self.config["vertical_label_strip_width"] + minor_label_width + self.config["data_grid_left_margin"]) * self.datapoint_width)
        self.base_data_zone_y = int((self.config["page_top_padding"] + self.config["label_strip_height"] + minor_label_height + self.config["data_grid_top_margin"]) * self.datapoint_height)
        
        # Calculate base label zone boundaries (for page 0)
        self.base_hlabel_zone_x = self.base_data_zone_x
        self.base_hlabel_zone_y = int(self.config["page_top_padding"] * self.datapoint_height)
        self.base_hlabel_zone_width = self.page_data_grid_width
        self.base_hlabel_zone_height = int(self.config["label_strip_height"] * self.datapoint_height)
        
        self.base_minor_hlabel_zone_x = self.base_data_zone_x
        self.base_minor_hlabel_zone_y = int((self.config["page_top_padding"] + self.config["label_strip_height"]) * self.datapoint_height)
        self.base_minor_hlabel_zone_width = self.page_data_grid_width
        self.base_minor_hlabel_zone_height = int(self.config["minor_label_strip_height"] * self.datapoint_height)
        
        self.base_vlabel_zone_x = int(self.config["page_left_padding"] * self.datapoint_width)
        self.base_vlabel_zone_y = self.base_data_zone_y
        self.base_vlabel_zone_width = int(self.config["vertical_label_strip_width"] * self.datapoint_width)
        self.base_vlabel_zone_height = self.page_data_grid_height
        
        self.base_minor_vlabel_zone_x = int((self.config["page_left_padding"] + self.config["vertical_label_strip_width"]) * self.datapoint_width)
        self.base_minor_vlabel_zone_y = self.base_data_zone_y
        self.base_minor_vlabel_zone_width = int(self.config["vertical_minor_label_strip_width"] * self.datapoint_width)
        self.base_minor_vlabel_zone_height = self.page_data_grid_height
        
        # Legend zone (not affected by pages)
        self.legend_zone_y = int((self.config["page_top_padding"] + self.config["label_strip_height"] + minor_label_height + self.config["data_grid_top_margin"] + (self.page_data_grid_height // self.datapoint_height) + self.config["data_grid_bottom_margin"]) * self.datapoint_height)
        
        # Initialize graphics device/surface
        self.img = Image.new('RGB', (self.img_width, self.img_height), color='black')
        self.draw = ImageDraw.Draw(self.img)
    
    def _calculate_grid_page_size(self) -> tuple:
        """Calculate the size of a single grid page in model units"""
        minor_label_width = self.config["vertical_minor_label_strip_width"] if self.intracell_rows > 1 else 0
        minor_label_height = self.config["minor_label_strip_height"] if self.intracell_cols > 1 else 0
        
        grid_page_width_model = (
            self.config["vertical_label_strip_width"] +
            minor_label_width +
            self.config["data_grid_left_margin"] +
            (self.page_data_grid_width // self.datapoint_width) +
            self.config["data_grid_right_margin"]
        )
        
        #print(f'DEBUG: grid_page_width_model: {grid_page_width_model}, vertical_label_strip_width: {self.config["vertical_label_strip_width"]}, minor_label_width: {minor_label_width}, data_grid_left_margin: {self.config["data_grid_left_margin"]}, (self.page_data_grid_width // self.datapoint_width): {(self.page_data_grid_width // self.datapoint_width)}, page_data_grid_width: {self.page_data_grid_width}, datapoint_width: {self.datapoint_width}, data_grid_right_margin: {self.config["data_grid_right_margin"]}')
        
        grid_page_height_model = (
            self.config["label_strip_height"] +
            minor_label_height +
            self.config["data_grid_top_margin"] +
            (self.page_data_grid_height // self.datapoint_height) +
            self.config["data_grid_bottom_margin"]
        )
        
        return (grid_page_width_model, grid_page_height_model)
    
    def _get_page_offset(self, page_number: int) -> tuple:
        """Calculate page offset for given page number"""
        grid_page_width_model, grid_page_height_model = self._calculate_grid_page_size()
        
        if self.layout_mode == "zicv":
            # ZICV: Vertical offset for each grid page
            offset_x = 0
            offset_y = page_number * int(grid_page_height_model * self.datapoint_height)
        else:  # zich
            # ZICH: Horizontal offset for each grid page
            offset_x = page_number * int(grid_page_width_model * self.datapoint_width)
            offset_y = 0
        
        return (offset_x, offset_y)
    
    def _get_font_sizes(self):
        """Calculate font sizes based on datapoint dimensions from config"""
        datapoint_width = self.config["DATAPOINT_WIDTH_PX"]
        datapoint_height = self.config["DATAPOINT_HEIGHT_PX"]
        
        # Calculate diagonal for 45-degree rotated labels
        diagonal = math.sqrt(datapoint_width**2 + datapoint_height**2)
        
        return {
            "horizontal_major": int(datapoint_width * self.config["horizontal_label_font_ratio"]),
            "horizontal_45deg": int(diagonal * self.config["horizontal_label_45deg_font_ratio"]),
            "vertical": int(datapoint_height * self.config["vertical_label_font_ratio"]),
            "title": int(datapoint_height * self.config["title_font_ratio"])
        }
    
    def _get_font(self, font_type: str):
        """Get font object for specified type with appropriate size"""
        if font_type == "title":
            font_name = self.config["title_font_name"]
        elif "horizontal" in font_type:
            font_name = self.config["horizontal_label_font_name"]
        else:
            font_name = self.config["vertical_label_font_name"]
        
        if font_type == "horizontal_major":
            font_size = self.font_sizes["horizontal_major"]
        elif font_type == "horizontal_45deg":
            font_size = self.font_sizes["horizontal_45deg"]
        elif font_type == "vertical":
            font_size = self.font_sizes["vertical"]
        elif font_type == "title":
            font_size = self.font_sizes["title"]
        else:
            # Fallback to horizontal major
            font_size = self.font_sizes["horizontal_major"]
        
        try:
            return ImageFont.truetype(font_name, font_size)
        except:
            return ImageFont.load_default()
    
    def draw_vertical_text_bottom_aligned(self, text: str, font, fg_color, left_x: int, right_x: int, top_y: int, bottom_y: int, rotation: int = 90):
        """Draw vertical text bottom-aligned using manual coordinate math"""
        # Step 1: Get text dimensions
        bbox = ImageDraw.Draw(Image.new('RGBA', (1, 1))).textbbox((0, 0), text, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
        
        # Step 2: Create temp image and draw text left-aligned
        padding = max(self.font_sizes.values())  # Use largest font size for padding
        temp_img = Image.new('RGBA', (text_width + 2*padding, text_height + 2*padding), (0, 0, 0, 0))
        temp_draw = ImageDraw.Draw(temp_img)
        temp_draw.text((padding, padding), text, fill=fg_color, font=font)

        
        # Step 3: Rotate around image center
        rotated = temp_img.rotate(rotation, expand=True)
        
        # Step 4: Calculate positioning based on rotation angle
        target_x = left_x + (right_x - left_x) // 2   # label center horizontally
        target_y = bottom_y                           # label bottom
        
        if rotation == 90:
            # Simple case - 90° rotation
            paste_x = target_x - rotated.width // 2
            paste_y = target_y - rotated.height
        else:
            # Complex case - need to track pivot point through rotation
            import math
            
            # Original pivot point: center-left of text (0, text_height/2)
            pivot_x_orig = 0
            pivot_y_orig = text_height / 2
            
            # Center of original image
            center_x = text_width / 2
            center_y = text_height / 2
            
            # Pivot relative to center
            rel_x = pivot_x_orig - center_x
            rel_y = pivot_y_orig - center_y
            
            # Apply rotation around center
            angle_rad = math.radians(-rotation)  # Negative for clockwise
            rotated_rel_x = rel_x * math.cos(angle_rad) - rel_y * math.sin(angle_rad)
            rotated_rel_y = rel_x * math.sin(angle_rad) + rel_y * math.cos(angle_rad)
            
            # New pivot position in rotated image
            pivot_x_rotated = rotated.width / 2 + rotated_rel_x
            pivot_y_rotated = rotated.height / 2 + rotated_rel_y
            
            # Position image so pivot is at target location
            paste_x = int(target_x - pivot_x_rotated)
            paste_y = int(target_y - pivot_y_rotated)
        
        self.img.paste(rotated, (paste_x, paste_y), rotated)
    
    def _model_to_view(self, page_number: int, grid_col: int, grid_row: int, intracell_col: int = 0, intracell_row: int = 0) -> tuple:
        """Convert model coordinates to pixel coordinates within data zone for specific page"""
        offset_x, offset_y = self._get_page_offset(page_number)
        
        pixel_x = self.base_data_zone_x + offset_x + grid_col * self.cell_width + intracell_col * self.datapoint_width
        pixel_y = self.base_data_zone_y + offset_y + grid_row * self.cell_height + intracell_row * self.datapoint_height
        return (pixel_x, pixel_y)
    
    def _legend_to_view(self, legend_col: int, legend_row: int) -> tuple:
        """Convert legend coordinates to pixel coordinates within legend zone"""
        pixel_x = self.base_data_zone_x + legend_col * self.datapoint_width  # Align with data zone
        pixel_y = self.legend_zone_y + legend_row * self.datapoint_height
        return (pixel_x, pixel_y)
    
    def draw_datapoint(self, page_number: int, grid_col: int, grid_row: int, intracell_col: int, intracell_row: int, color: tuple):
        """Draw datapoint using model coordinates for specific page"""
        pixel_x, pixel_y = self._model_to_view(page_number, grid_col, grid_row, intracell_col, intracell_row)
        # Draw rectangle at pixel coordinates
        self.draw.rectangle([
            pixel_x, pixel_y,
            pixel_x + self.datapoint_width - 1, pixel_y + self.datapoint_height - 1
        ], fill=color)
    
    def draw_grid_lines(self, page_number: int):
        """Draw grid lines starting from grid edge for specific page"""
        grid_h_spacing = self.config["gridHSpacingPx"]
        grid_v_spacing = self.config["gridVSpacingPx"]
        grid_color = self.config["gridLinesColor"]
        minor_grid_color = self.config["minorGridLinesColor"]
        
        # Get page offset
        offset_x, offset_y = self._get_page_offset(page_number)
        
        # Calculate page-specific data zone boundaries
        data_zone_x = self.base_data_zone_x + offset_x
        data_zone_y = self.base_data_zone_y + offset_y
        data_zone_width = self.page_data_grid_width
        data_zone_height = self.page_data_grid_height
        
        # Calculate basic line boundaries for this page
        left_boundary = data_zone_x - int(self.config["data_grid_left_margin"] * self.datapoint_width)
        right_boundary = data_zone_x + data_zone_width + int(self.config["data_grid_right_margin"] * self.datapoint_width)
        top_boundary = data_zone_y - int(self.config["data_grid_top_margin"] * self.datapoint_height)
        bottom_boundary = data_zone_y + data_zone_height + int(self.config["data_grid_bottom_margin"] * self.datapoint_height)
        
        # Check for color indicators in each direction
        has_vertical_indicators = self.intracell_cols > 1  # Top/bottom indicators
        has_horizontal_indicators = self.intracell_rows > 1  # Left/right indicators
        
        # Set boundaries based on color indicator presence
        indicator_size = self.config["metric_color_indicator_size"]
        
        # Vertical boundaries (for horizontal lines)
        if has_horizontal_indicators:
            left_boundary_h = left_boundary - int(indicator_size * self.datapoint_width)
            right_boundary_h = right_boundary + int(indicator_size * self.datapoint_width)
        else:
            left_boundary_h = left_boundary
            right_boundary_h = right_boundary
        
        # Horizontal boundaries (for vertical lines)
        if has_vertical_indicators:
            top_boundary_v = top_boundary - int(indicator_size * self.datapoint_height)
            bottom_boundary_v = bottom_boundary + int(indicator_size * self.datapoint_height)
        else:
            top_boundary_v = top_boundary
            bottom_boundary_v = bottom_boundary
        
        # Calculate grid dimensions for this page
        if self.layout_mode == "zicv":
            page_grid_cols = self.cells_per_page
            page_grid_rows = self.orthogonal_cells
        else:  # zich
            page_grid_cols = self.orthogonal_cells
            page_grid_rows = self.cells_per_page
        
        # Draw major horizontal lines starting from grid edge
        for row in range(page_grid_rows + 1):  # Include edge lines
            line_y = data_zone_y + row * self.cell_height
            for y in range(line_y, line_y + grid_v_spacing):
                if y <= data_zone_y + data_zone_height:  # Stay within bounds
                    self.draw.line([
                        (left_boundary_h, y),
                        (right_boundary_h - 1, y)
                    ], fill=grid_color)
        
        # Draw major vertical lines starting from grid edge
        for col in range(page_grid_cols + 1):  # Include edge lines
            line_x = data_zone_x + col * self.cell_width
            for x in range(line_x, line_x + grid_h_spacing):
                if x <= data_zone_x + data_zone_width:  # Stay within bounds
                    self.draw.line([
                        (x, top_boundary_v),
                        (x, bottom_boundary_v - 1)
                    ], fill=grid_color)
        
        # Draw minor grid lines (intracell separation)
        if self.intracell_cols > 1:
            # Intracell data laid out in columns - draw vertical minor lines
            for row in range(page_grid_rows):
                for col in range(page_grid_cols):
                    cell_left = data_zone_x + col * self.cell_width
                    
                    # Draw vertical lines between intracell columns
                    for intracell_col in range(1, self.intracell_cols):
                        line_x = cell_left + intracell_col * self.datapoint_width
                        for x in range(line_x, line_x + grid_h_spacing):
                            if x <= data_zone_x + data_zone_width:
                                self.draw.line([
                                    (x, top_boundary_v),
                                    (x, bottom_boundary_v - 1)
                                ], fill=minor_grid_color)
        
        elif self.intracell_rows > 1:
            # Intracell data laid out in rows - draw horizontal minor lines
            for row in range(page_grid_rows):
                for col in range(page_grid_cols):
                    cell_top = data_zone_y + row * self.cell_height
                    
                    # Draw horizontal lines between intracell rows
                    for intracell_row in range(1, self.intracell_rows):
                        line_y = cell_top + intracell_row * self.datapoint_height
                        for y in range(line_y, line_y + grid_v_spacing):
                            if y <= data_zone_y + data_zone_height:
                                self.draw.line([
                                    (left_boundary_h, y),
                                    (right_boundary_h - 1, y)
                                ], fill=minor_grid_color)
    

    def draw_horizontal_indicators_full_grid(self, page_number: int, min_color: tuple, max_color: tuple):
        """Draw horizontal indicators spanning the entire data grid"""
        indicator_size = self.config["metric_color_indicator_size"]
        bar_height = int(indicator_size * self.datapoint_height)
    
        # Get page offset
        offset_x, offset_y = self._get_page_offset(page_number)
        data_zone_x = self.base_data_zone_x + offset_x
        data_zone_y = self.base_data_zone_y + offset_y
    
        # Top bar (max color)
        top_y = data_zone_y - bar_height
        self.draw.rectangle([
            data_zone_x, top_y,
            data_zone_x + self.page_data_grid_width - 1, data_zone_y - 1
        ], fill=max_color)
    
        # Bottom bar (min color)
        bottom_y = data_zone_y + self.page_data_grid_height
        self.draw.rectangle([
            data_zone_x, bottom_y,
            data_zone_x + self.page_data_grid_width - 1, bottom_y + bar_height - 1
        ], fill=min_color)

    def draw_horizontal_indicators_grid_cell(self, page_number: int, grid_col: int, min_color: tuple, max_color: tuple):
        """Draw horizontal indicators spanning a single grid cell"""
        indicator_size = self.config["metric_color_indicator_size"]
        bar_height = int(indicator_size * self.datapoint_height)
    
        # Get page offset
        offset_x, offset_y = self._get_page_offset(page_number)
        data_zone_x = self.base_data_zone_x + offset_x
        data_zone_y = self.base_data_zone_y + offset_y
    
        # Calculate cell boundaries
        col_left = data_zone_x + grid_col * self.cell_width
        col_right = col_left + self.cell_width
    
        # Top bar (max color)
        top_y = data_zone_y - bar_height
        self.draw.rectangle([
            col_left, top_y,
            col_right - 1, data_zone_y - 1
        ], fill=max_color)
    
        # Bottom bar (min color)
        bottom_y = data_zone_y + self.page_data_grid_height
        self.draw.rectangle([
            col_left, bottom_y,
            col_right - 1, bottom_y + bar_height - 1
        ], fill=min_color)

    def draw_horizontal_indicators_intracell_column(self, page_number: int, grid_row: int, grid_col: int, intracell_col: int, min_color: tuple, max_color: tuple):
        """Draw horizontal indicators spanning a single intracell column"""
        indicator_size = self.config["metric_color_indicator_size"]
        bar_height = int(indicator_size * self.datapoint_height)
    
        # Get page offset
        offset_x, offset_y = self._get_page_offset(page_number)
        data_zone_x = self.base_data_zone_x + offset_x
        data_zone_y = self.base_data_zone_y + offset_y
    
        # Calculate intracell column boundaries
        col_left = data_zone_x + grid_col * self.cell_width + intracell_col * self.datapoint_width
        col_right = col_left + self.datapoint_width
    
        # Top bar (max color)
        top_y = data_zone_y - bar_height
        self.draw.rectangle([
            col_left, top_y,
            col_right - 1, data_zone_y - 1
        ], fill=max_color)
    
        # Bottom bar (min color)
        bottom_y = data_zone_y + self.page_data_grid_height
        self.draw.rectangle([
            col_left, bottom_y,
            col_right - 1, bottom_y + bar_height - 1
        ], fill=min_color)

    def draw_vertical_indicators_grid_cell(self, page_number: int, grid_row: int, min_color: tuple, max_color: tuple):
        """Draw vertical indicators spanning a single grid cell"""
        indicator_size = self.config["metric_color_indicator_size"]
        bar_width = int(indicator_size * self.datapoint_width)
    
        # Get page offset
        offset_x, offset_y = self._get_page_offset(page_number)
        data_zone_x = self.base_data_zone_x + offset_x
        data_zone_y = self.base_data_zone_y + offset_y
    
        # Calculate cell boundaries
        row_top = data_zone_y + grid_row * self.cell_height
        row_bottom = row_top + self.cell_height
    
        # Left bar (max color)
        left_x = data_zone_x - bar_width
        self.draw.rectangle([
            left_x, row_top,
            data_zone_x - 1, row_bottom - 1
        ], fill=max_color)
    
        # Right bar (min color)
        right_x = data_zone_x + self.page_data_grid_width
        self.draw.rectangle([
            right_x, row_top,
            right_x + bar_width - 1, row_bottom - 1
        ], fill=min_color)

    def draw_vertical_indicators_intracell_row(self, page_number: int, grid_row: int, grid_col: int, intracell_row: int, min_color: tuple, max_color: tuple):
        """Draw vertical indicators spanning a single intracell row"""
        indicator_size = self.config["metric_color_indicator_size"]
        bar_width = int(indicator_size * self.datapoint_width)
    
        # Get page offset
        offset_x, offset_y = self._get_page_offset(page_number)
        data_zone_x = self.base_data_zone_x + offset_x
        data_zone_y = self.base_data_zone_y + offset_y
    
        # Calculate intracell row boundaries
        row_top = data_zone_y + grid_row * self.cell_height + intracell_row * self.datapoint_height
        row_bottom = row_top + self.datapoint_height
    
        # Left bar (max color)
        left_x = data_zone_x - bar_width
        self.draw.rectangle([
            left_x, row_top,
            data_zone_x - 1, row_bottom - 1
        ], fill=max_color)
    
        # Right bar (min color)
        right_x = data_zone_x + self.page_data_grid_width
        self.draw.rectangle([
            right_x, row_top,
            right_x + bar_width - 1, row_bottom - 1
        ], fill=min_color)

    def draw_metric_color_indicators(self, page_number: int, axis_type: str, z_mode: str, metrics_info: list):
        """
        Draw min/max color indicator bars for metrics for specific page
    
        Args:
            page_number: Page number for positioning
            axis_type: "z-file", "z-intracell", "x-axis", "y-axis"
            z_mode: "zicv" (vertical intracell) or "zich" (horizontal intracell)
            metrics_info: List of dicts with {metric_index, min_color, max_color}
        """
        # Calculate grid dimensions for this page
        if self.layout_mode == "zicv":
            page_grid_cols = self.cells_per_page
            page_grid_rows = self.orthogonal_cells
        else:  # zich
            page_grid_cols = self.orthogonal_cells
            page_grid_rows = self.cells_per_page
    
        if axis_type == "z-file":
            # Full-width horizontal bars above and below entire grid
            if metrics_info:
                metric = metrics_info[0]  # Single metric in file mode
                self.draw_horizontal_indicators_full_grid(page_number, metric['min_color'], metric['max_color'])
    
        elif axis_type == "z-intracell":
            if z_mode == "zicv":  # Vertical intracell (metrics as columns)
                # Horizontal bars above/below each intracell column in EVERY grid cell
                for metric in metrics_info:
                    intracell_col = metric['metric_index']
                
                    # Draw bars for every grid cell on this page
                    for row in range(page_grid_rows):
                        for col in range(page_grid_cols):
                            self.draw_horizontal_indicators_intracell_column(
                                page_number, row, col, intracell_col, 
                                metric['min_color'], metric['max_color']
                            )
        
            else:  # zich - Horizontal intracell (metrics as rows)
                # Vertical bars left/right of each intracell row in EVERY grid cell
                for metric in metrics_info:
                    intracell_row = metric['metric_index']
                
                    # Draw bars for every grid cell on this page
                    for row in range(page_grid_rows):
                        for col in range(page_grid_cols):
                            self.draw_vertical_indicators_intracell_row(
                                page_number, row, col, intracell_row,
                                metric['min_color'], metric['max_color']
                            )
    
        elif axis_type == "x-axis":
            # Horizontal bars above/below grid columns
            for metric in metrics_info:
                grid_col = metric['grid_position']
                self.draw_horizontal_indicators_grid_cell(
                    page_number, grid_col, 
                    metric['min_color'], metric['max_color']
                )
    
        elif axis_type == "y-axis":
            # Vertical bars left/right of grid rows
            for metric in metrics_info:
                grid_row = metric['grid_position']
                self.draw_vertical_indicators_grid_cell(
                    page_number, grid_row,
                    metric['min_color'], metric['max_color']
                )

    
    def draw_hlabel_strip(self, page_number: int, grid_col: int, text: str):
        """Draw horizontal label strip label for specific page"""
        grid_v_spacing = self.config["gridVSpacingPx"]
        grid_h_spacing = self.config["gridHSpacingPx"]
        
        # Get page offset
        offset_x, offset_y = self._get_page_offset(page_number)
        hlabel_zone_x = self.base_hlabel_zone_x + offset_x
        hlabel_zone_y = self.base_hlabel_zone_y + offset_y
        
        # Calculate label box boundaries (between major grid lines, excluding grid line space)
        left_x = hlabel_zone_x + grid_col * self.cell_width + grid_h_spacing
        right_x = left_x + self.cell_width - grid_h_spacing
        top_y = hlabel_zone_y
        bottom_y = top_y + self.base_hlabel_zone_height - grid_v_spacing  # Subtract one spacing height
        
        # Draw background box
        bg_color = self.config["horizontal_label_bg_color"]
        self.draw.rectangle([left_x, top_y, right_x - 1, bottom_y - 1], fill=bg_color)
        
        # Draw text
        fg_color = self.config["horizontal_label_fg_color"]
        
        # Determine text orientation
        if self.intracell_cols > 1:
            # Horizontal text when there are minor labels
            font = self._get_font("horizontal_major")
            bbox = self.draw.textbbox((0, 0), text, font=font)
            text_width = bbox[2] - bbox[0]
            text_height = bbox[3] - bbox[1]
            
            # Center text in box
            text_x = left_x + ((right_x - left_x) - text_width) // 2
            text_y = top_y + ((bottom_y - top_y) - text_height) // 2
            
            self.draw.text((text_x, text_y), text, fill=fg_color, font=font)
        else:
            # 45-degree text when there are no minor labels (same as minor label rendering)
            font = self._get_font("horizontal_45deg")
            self.draw_vertical_text_bottom_aligned(text, font, fg_color, left_x, right_x, top_y, bottom_y, rotation=45)
    
    def draw_intracell_hlabel_strip(self, page_number: int, grid_col: int, intracell_col: int, text: str):
        """Draw intracell horizontal label strip label for specific page"""
        grid_v_spacing = self.config["gridVSpacingPx"]
        grid_h_spacing = self.config["gridHSpacingPx"]
        
        # Get page offset
        offset_x, offset_y = self._get_page_offset(page_number)
        minor_hlabel_zone_x = self.base_minor_hlabel_zone_x + offset_x
        minor_hlabel_zone_y = self.base_minor_hlabel_zone_y + offset_y
        
        # Calculate label box boundaries (between minor grid lines, excluding grid line space)
        cell_left = minor_hlabel_zone_x + grid_col * self.cell_width
        left_x = cell_left + intracell_col * self.datapoint_width + grid_h_spacing
        right_x = left_x + self.datapoint_width - grid_h_spacing
        top_y = minor_hlabel_zone_y
        bottom_y = top_y + self.base_minor_hlabel_zone_height - grid_v_spacing
        
        # Draw background box
        bg_color = self.config["horizontal_label_bg_color"]
        self.draw.rectangle([left_x, top_y, right_x - 1, bottom_y - 1], fill=bg_color)
        
        # Load font (45-degree rotation)
        font = self._get_font("horizontal_45deg")
        
        # Draw text (45° rotation for intracell labels) - bottom-aligned
        fg_color = self.config["horizontal_label_fg_color"]
        self.draw_vertical_text_bottom_aligned(text, font, fg_color, left_x, right_x, top_y, bottom_y, rotation=45)
    
    def draw_vlabel_strip(self, page_number: int, grid_row: int, text: str):
        """Draw vertical label strip label for specific page"""
        grid_h_spacing = self.config["gridHSpacingPx"]
        grid_v_spacing = self.config["gridVSpacingPx"]
        
        # Get page offset
        offset_x, offset_y = self._get_page_offset(page_number)
        vlabel_zone_x = self.base_vlabel_zone_x + offset_x
        vlabel_zone_y = self.base_vlabel_zone_y + offset_y
        
        # Calculate label box boundaries
        left_x = vlabel_zone_x
        right_x = left_x + self.base_vlabel_zone_width - grid_h_spacing
        top_y = vlabel_zone_y + grid_row * self.cell_height + grid_v_spacing
        bottom_y = top_y + self.cell_height - grid_v_spacing
        
        # Draw background box
        bg_color = self.config["vertical_label_bg_color"]
        self.draw.rectangle([left_x, top_y, right_x - 1, bottom_y - 1], fill=bg_color)
        
        # Load font
        font = self._get_font("vertical")
        
        # Draw horizontal text (no rotation needed)
        fg_color = self.config["vertical_label_fg_color"]
        bbox = self.draw.textbbox((0, 0), text, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
        
        # Center text in box
        text_x = left_x + ((right_x - left_x) - text_width) // 2
        text_y = top_y + ((bottom_y - top_y) - text_height) // 2
        
        self.draw.text((text_x, text_y), text, fill=fg_color, font=font)
    
    def draw_intracell_vlabel_strip(self, page_number: int, grid_row: int, intracell_row: int, text: str):
        """Draw intracell vertical label strip label for specific page"""
        grid_h_spacing = self.config["gridHSpacingPx"]
        grid_v_spacing = self.config["gridVSpacingPx"]
        
        # Get page offset
        offset_x, offset_y = self._get_page_offset(page_number)
        minor_vlabel_zone_x = self.base_minor_vlabel_zone_x + offset_x
        minor_vlabel_zone_y = self.base_minor_vlabel_zone_y + offset_y
        
        # Calculate label box boundaries
        left_x = minor_vlabel_zone_x
        right_x = left_x + self.base_minor_vlabel_zone_width - grid_h_spacing
        cell_top = minor_vlabel_zone_y + grid_row * self.cell_height
        top_y = cell_top + intracell_row * self.datapoint_height + grid_v_spacing
        bottom_y = top_y + self.datapoint_height - grid_v_spacing
        
        # Draw background box
        bg_color = self.config["vertical_label_bg_color"]
        self.draw.rectangle([left_x, top_y, right_x - 1, bottom_y - 1], fill=bg_color)
        
        # Load font
        font = self._get_font("vertical")
        
        # Draw horizontal text (no rotation needed)
        fg_color = self.config["vertical_label_fg_color"]
        bbox = self.draw.textbbox((0, 0), text, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
        
        # Center text in box
        text_x = left_x + ((right_x - left_x) - text_width) // 2
        text_y = top_y + ((bottom_y - top_y) - text_height) // 2
        
        self.draw.text((text_x, text_y), text, fill=fg_color, font=font)
    
    def draw_label(self, grid_col: int, grid_row: int, text: str, label_type: str):
        """DEPRECATED: Use specific label drawing functions instead"""
        # For now, redirect to hlabel_strip with page 0
        if label_type == 'col_header':
            self.draw_hlabel_strip(0, grid_col, text)
        # TODO: Add other label types as they're implemented
        pass
    
    def draw_title(self, title_text: str):
        """Draw title at top left inside page padding (for Z-file mode)"""
        # Calculate title position
        title_x = int(self.config["page_left_padding"] * self.datapoint_width)
        title_y = int((self.config["page_top_padding"] + self.config["title_top_margin"]) * self.datapoint_height)
        
        # Get title font and color
        font = self._get_font("title")
        fg_color = self.config["title_fg_color"]
        
        # Draw title text
        self.draw.text((title_x, title_y), title_text, fill=fg_color, font=font)
    
    def draw_legend(self, legend_col: int, legend_row: int, text: str):
        """NOOP legend text drawing function using legend coordinates"""
        pixel_x, pixel_y = self._legend_to_view(legend_col, legend_row)
        # TODO: Draw legend text at calculated position
        pass
    
    def save(self, filepath: str):
        """Save graphics device content to file"""
        self.img.save(filepath)
        #print(f"DEBUG: save {filepath}")
