import os
import sys
import math
import json
import subprocess
import platform

# ĐOẠN THÊM MỚI: Tắt tính năng mô phỏng cảm ứng chuột phải (Xóa hoàn toàn dấu chấm tròn đỏ)
from kivy.config import Config
Config.set('input', 'mouse', 'mouse,disable_multitouch')

if platform.system() == "Windows":
    try:
        import win32timezone
    except ImportError:
        pass

from kivy.app import App
from kivy.uix.widget import Widget
from kivy.clock import Clock
from kivy.graphics import Color, Mesh, PushMatrix, PopMatrix, Rotate, Translate, RenderContext
from kivy.graphics.instructions import Callback 
from kivy.graphics.opengl import glEnable, glDisable, GL_DEPTH_TEST
from kivy.graphics.transformation import Matrix
from kivy.core.window import Window
from kivy.uix.popup import Popup
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.uix.button import Button
from kivy.core.text import Label as CoreLabel
from kivy.core.audio import SoundLoader 
from kivy.uix.filechooser import FileChooserIconView
from kivy.core.image import Image as CoreImage

def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

def get_data_path(filename):
    if platform.system() == "Windows":
        base_dir = os.environ.get('APPDATA')
    else:
        base_dir = os.path.expanduser('~/.config')
        
    if not base_dir:
        base_dir = os.path.expanduser('~')
        
    app_dir = os.path.join(base_dir, 'RubikNotebook')
    if not os.path.exists(app_dir):
        try:
            os.makedirs(app_dir)
        except:
            return filename
            
    return os.path.join(app_dir, filename)


class RubikWidget(Widget):
    def __init__(self, **kwargs):
        self.canvas = RenderContext(compute_normal_mat=True)
        super(RubikWidget, self).__init__(**kwargs)
        
        self.angle_x, self.angle_y = 25, -45
        self.active_cubie = None 
        self.anim_val = 0.0
        
        self.zoom_scale = 7.0   
        self.min_zoom = 1.5     
        self.max_zoom = 25.0    
        self.touch_start_dist = 0 
        
        self.just_zoomed = False
        self.current_touches = {}
        self.is_moving = False
        
        self.touch_start_x = 0
        self.touch_start_y = 0

        self.idle_time = 0.0

        self.cubie_list = []
        idx = 1
        for x in [-1, 0, 1]:
            for y in [-1, 0, 1]:
                for z in [-1, 0, 1]:
                    if x == 0 and y == 0 and z == 0: 
                        continue
                    self.cubie_list.append({'x': x, 'y': y, 'z': z, 'num': idx})
                    idx += 1

        # --- BỔ SUNG BIẾN HOVER TẠI ĐÂY ---
        self.hovered_cubie = None 
        Window.bind(mouse_pos=self.on_mouse_hover_cubie)
        # ---------------------------------

        self.data_storage = {
            "global_notes": "", 
            "cubie_titles": {},   
            "cubie_notes": {},    
            "cubie_files": {},    
            "cubie_styles": {},   
            "face_images": {      
                'FRONT': '', 'BACK': '', 'RIGHT': '', 'LEFT': '', 'TOP': '', 'BOTTOM': ''
            }
        }
        self.texture_cache = {}
        self.face_texture_cache = {} 

        self.sound_open = None
        self.sound_close = None
        self.sound_typewriter = None
        
        sound_open_path = resource_path('open_drawer.wav')
        sound_close_path = resource_path('close_drawer.wav')
        sound_type_path = resource_path('typewriter.wav')
        
        try:
            if os.path.exists(sound_open_path):
                self.sound_open = SoundLoader.load(sound_open_path)
            if os.path.exists(sound_close_path):
                self.sound_close = SoundLoader.load(sound_close_path)
            if os.path.exists(sound_type_path):
                self.sound_typewriter = SoundLoader.load(sound_type_path)
        except: pass

        data_file_path = get_data_path("rubik_data.json")
        if os.path.exists(data_file_path):
            try:
                with open(data_file_path, 'r', encoding='utf-8') as f:
                    loaded_data = json.load(f)
                    if "cubie_notes" in loaded_data:
                        self.data_storage = loaded_data
            except: pass

        Window.bind(on_mouse_down=self.on_mouse_zoom)
        Clock.schedule_interval(self.update_gl, 1/60.)
        
        Clock.schedule_once(self.show_welcome_typewriter, 0.5)

    def show_welcome_typewriter(self, dt):
        welcome_text = "Chào    bạn,    chúc    bạn    một    ngày    vui    vẻ,    tràn    đầy    năng    lượng     tích    cực   ..."
        # ... giữ nguyên như bạn gửi ...
        content_layout = BoxLayout(orientation='vertical', padding=20, spacing=15)
        lbl_text = Label(
            text="", font_size='22sp', bold=True, color=(0, 1, 1, 1),
            halign='center', valign='middle'
        )
        lbl_text.bind(size=lbl_text.setter('text_size'))
        content_layout.add_widget(lbl_text)
        
        btn_skip = Button(
            text="VÀO HỆ THỐNG", size_hint=(None, None), size=(180, 45),
            pos_hint={'center_x': 0.5}, bold=True, background_color=(0, 0.5, 0.5, 1)
        )
        content_layout.add_widget(btn_skip)
        
        popup = Popup(
            title="KHỞI ĐỘNG COMPONENT", content=content_layout,
            size_hint=(0.75, 0.35), auto_dismiss=False,
            background_color=(0, 0, 0.2, 0.9)
        )
        btn_skip.bind(on_release=popup.dismiss)
        popup.open()
        
        self.char_idx = 0
        def type_tick(tick_dt):
            if not popup.parent:
                return False
                
            if self.char_idx < len(welcome_text):
                lbl_text.text += welcome_text[self.char_idx]
                self.char_idx += 1
                if self.sound_typewriter:
                    self.sound_typewriter.stop()
                    self.sound_typewriter.play()
                return True
            return False
            
        Clock.schedule_interval(type_tick, 0.06)

    # === BỔ SUNG HÀM XỬ LÝ HOVER MỚI VÀO TRONG CLASS RubikWidget ===
    def on_mouse_hover_cubie(self, window, pos):
        # Nếu đang mở UI ghi chú hoặc menu popup thì tạm dừng check hover 3D để tối ưu hiệu năng
        if self.active_cubie is not None:
            return False
            
        # Giả lập một touch object để tận dụng hàm find_clicked_cubie_robust có sẵn
        class DummyTouch:
            def __init__(self, x, y):
                self.x = x
                self.y = y
                
        # Chuyển đổi tọa độ cửa sổ sang tọa độ widget cục bộ
        local_pos = self.to_widget(*pos)
        dummy_touch = DummyTouch(local_pos[0], local_pos[1])
        
        # Tìm xem chuột có đang nằm trên cubie nào không
        hovered_num = self.find_clicked_cubie_robust(dummy_touch)
        
        # Nếu trạng thái hover thay đổi, cập nhật lại giao diện
        if hovered_num != self.hovered_cubie:
            self.hovered_cubie = hovered_num
            # Ép buộc vẽ lại Canvas ngay lập tức để tạo hiệu ứng mượt mà
            self.update_gl(0)
        return False

    # ... toàn bộ các hàm khác như bạn gửi ...
    # === BỔ SUNG LẠI HÀM ON_MOUSE_ZOOM BỊ THIẾU VÀO TRONG CLASS RubikWidget ===
    def on_mouse_zoom(self, window, x, y, button, modifiers):
        self.idle_time = 0.0
        if button in ('scrollup', 'scrolldown'):
            self.just_zoomed = True 
            if button == 'scrolldown':
                self.zoom_scale = min(self.max_zoom, self.zoom_scale + 0.4) 
                return True
            elif button == 'scrollup':
                self.zoom_scale = max(self.min_zoom, self.zoom_scale - 0.4) 
                return True
        return False
        
    def play_sound(self, sound_type):
        try:
            if sound_type == "open" and self.sound_open:
                self.sound_open.stop()
                self.sound_open.play()
            elif sound_type == "close" and self.sound_close:
                self.sound_close.stop()
                self.sound_close.play()
        except: pass

    def update_gl(self, dt):
        self.idle_time += dt
        
        if self.idle_time > 5.0 and self.active_cubie is None:
            self.angle_y += 0.25  
            self.angle_x = max(-30, min(40, self.angle_x + 0.03 * math.sin(self.angle_y * 0.02)))

        if self.active_cubie is not None:
            if self.anim_val < 1.0: self.anim_val += 0.15
        else:
            if self.anim_val > 0: self.anim_val -= 0.15
            
        self.canvas.clear()
        width = self.width if self.width > 100 else 800
        height = self.height if self.height > 100 else 600
        asp = width / float(height)
        
        proj = Matrix()
        if asp > 1.0:
            proj.view_clip(-self.zoom_scale * asp, self.zoom_scale * asp, -self.zoom_scale, self.zoom_scale, -100, 100, 0)
        else:
            proj.view_clip(-self.zoom_scale, self.zoom_scale, -self.zoom_scale / asp, self.zoom_scale / asp, -100, 100, 0)
            
        mv = Matrix()
        self.canvas['projection_mat'] = proj
        self.canvas['modelview_mat'] = mv

        with self.canvas:
            Callback(lambda instr: glEnable(GL_DEPTH_TEST))
            PushMatrix()
            Rotate(angle=self.angle_x, axis=(1, 0, 0))
            Rotate(angle=self.angle_y, axis=(0, 1, 0))
            
            for cubie in self.cubie_list:
                self.draw_drawer_neon_fixed(cubie['x'], cubie['y'], cubie['z'], cubie['num'])
                        
            PopMatrix()
            Callback(lambda instr: glDisable(GL_DEPTH_TEST))

    def get_face_texture(self, face_name):
        img_path = self.data_storage["face_images"].get(face_name, "")
        if not img_path or not os.path.exists(img_path):
            return None

        cached = self.face_texture_cache.get(face_name)
        if cached:
            last_mod_time = os.path.getmtime(img_path)
            if cached.get("path") != img_path or cached.get("mod_time") != last_mod_time:
                cached = None

        if not cached:
            try:
                kivy_img = CoreImage(img_path)
                self.face_texture_cache[face_name] = {
                    "tex": kivy_img.texture,
                    "path": img_path,
                    "mod_time": os.path.getmtime(img_path)
                }
            except Exception:
                return None

        return self.face_texture_cache[face_name]["tex"]

    def determine_primary_face(self, cx, cy, cz):
        if cz == 1:
            return 'FRONT'
        elif cz == -1:
            return 'BACK'
        elif cx == 1:
            return 'RIGHT'
        elif cx == -1:
            return 'LEFT'
        elif cy == 1:
            return 'TOP'
        elif cy == -1:
            return 'BOTTOM'
        else:
            return 'FRONT'

    # === THAY THẾ TOÀN BỘ HÀM draw_drawer_neon_fixed TRONG RubikWidget ===
    def draw_drawer_neon_fixed(self, cx, cy, cz, c_num):
        PushMatrix()

        gap_ratio = 0.1
        spacing = 2.0 + (gap_ratio * 1.6 / 3.0)
        Translate(cx * spacing, cy * spacing, cz * spacing)

        if self.active_cubie == c_num:
            Translate(cx * self.anim_val * 1.8, cy * self.anim_val * 1.8, cz * self.anim_val * 1.8)

        # Trạng thái kiểm tra xem ô hiện tại có đang được hover hay không
        is_hovered = (self.hovered_cubie == c_num)

        color_map = {
            'FRONT': (0, 0.4, 0.8, 1), 'BACK': (1, 0.5, 0.0, 1),
            'RIGHT': (0, 0.7, 0, 1), 'LEFT': (0.9, 0, 0, 1),
            'TOP': (1, 0.9, 0, 1), 'BOTTOM': (1, 1, 1, 1)
        }
        primary_face = self.determine_primary_face(cx, cy, cz)

        total_units = 3.0 + gap_ratio * 2
        u_start = (cx + 1 + gap_ratio) / total_units
        v_start = (cy + 1 + gap_ratio) / total_units
        u_end = u_start + 1 / total_units
        v_end = v_start + 1 / total_units

        sub_faces = [
            ('FRONT', 0, (0,1,0), cz==1, u_start, v_start, u_end, v_end),
            ('BACK', 180, (0,1,0), cz==-1, (-cx + 1 + gap_ratio) / total_units, v_start,
             (-cx + 1 + gap_ratio + 1) / total_units, v_end),
            ('RIGHT', 90, (0,1,0), cx==1, (-cz + 1 + gap_ratio) / total_units, v_start,
             (-cz + 1 + gap_ratio + 1) / total_units, v_end),
            ('LEFT', -90, (0,1,0), cx==-1, (cz + 1 + gap_ratio) / total_units, v_start,
             (cz + 1 + gap_ratio + 1) / total_units, v_end),
            ('TOP', -90, (1,0,0), cy==1, u_start, (-cz + 1 + gap_ratio) / total_units,
             u_end, (-cz + 1 + gap_ratio + 1) / total_units),
            ('BOTTOM', 90, (1,0,0), cy==-1, u_start, (cz + 1 + gap_ratio) / total_units,
             u_end, (cz + 1 + gap_ratio + 1) / total_units)
        ]
        key_str = str(c_num)

        for name, ang, ax, is_outer, u_offset, v_offset, u2, v2 in sub_faces:
            PushMatrix()
            if ang != 0:
                Rotate(angle=ang, axis=ax)
            Translate(0, 0, 1.0)

            if is_outer:
                face_tex = self.get_face_texture(name)
                if face_tex:
                    # Nếu ô được hover, nhân thêm độ sáng cho kết cấu ảnh (phát sáng)
                    if is_hovered:
                        Color(1.5, 1.5, 1.5, 1)
                    else:
                        Color(1, 1, 1, 1)
                    Mesh(vertices=[
                            -1,-1,0, u_offset, 1.0 - v_offset,
                             1,-1,0, u2, 1.0 - v_offset,
                             1, 1,0, u2, 1.0 - v2,
                            -1, 1,0, u_offset, 1.0 - v2
                        ],
                         indices=[0,1,2,2,3,0], mode='triangles', texture=face_tex,
                         fmt=[(b'vPosition', 3, 'float'), (b'vTexCoords0', 2, 'float')])
                else:
                    # Tạo hiệu ứng đổi màu nhẹ hoặc tăng mạnh độ sáng của màu nền khi di chuột vào
                    base_color = color_map[name]
                    if is_hovered:
                        # Tăng cường hiệu ứng Neon sáng rực bằng cách tăng giá trị RGB
                        Color(min(1.0, base_color[0] * 1.4), min(1.0, base_color[1] * 1.4), min(1.0, base_color[2] * 1.4), 1)
                    else:
                        Color(*base_color)
                    self._draw_mesh()
            else:
                Color(0.18, 0.18, 0.18, 1)
                self._draw_mesh()

            # Vẽ số ngăn / Tên ngăn kết hợp hiệu ứng thay đổi màu chữ/màu viền tròn khi Hover
            if is_outer and (name == primary_face):
                custom_title = self.data_storage["cubie_titles"].get(key_str, "")
                Translate(0, 0, 0.03)
                if custom_title:
                    # Nếu được hover, tên ngăn sẽ chuyển sang màu xanh chuối neon sáng để nổi bật
                    if is_hovered:
                        Color(0.2, 1.0, 0.2, 1)
                    else:
                        Color(1, 1, 1, 1)
                    self._draw_mesh(texture=self.get_tex(f"TITLE_{key_str}", custom_title, is_badge=False))
                else:
                    # Tạo hiệu ứng đổi màu viền tròn ô số từ Cyan sang Cam Neon khi di chuột
                    if is_hovered:
                        Color(1, 0.5, 0, 1) # Viền cam rực
                    else:
                        Color(0, 1, 1, 1) # Viền xanh neon mặc định
                        
                    self._draw_circle_mesh(radius=0.45)
                    Translate(0, 0, 0.01)
                    
                    Color(0, 0, 0, 1)
                    display_label = f"{c_num:02d}"
                    self._draw_label_mesh_small(texture=self.get_tex(f"NEON_{key_str}", display_label, is_badge=True))
            PopMatrix()
        PopMatrix()

    def get_tex(self, key, text, is_badge=False):
        if key not in self.texture_cache or self.texture_cache[key]['text'] != text:
            if is_badge:
                l = CoreLabel(text=text, font_size=18, color=(0, 0, 0, 1), bold=True)
            else:
                l = CoreLabel(text=text, font_size=24, color=(1, 1, 1, 1), bold=False)
            l.refresh()
            self.texture_cache[key] = {'tex': l.texture, 'text': text}
        return self.texture_cache[key]['tex']

    def _draw_mesh(self, texture=None):
        Mesh(vertices=[-1,-1,0,0,1, 1,-1,0,1,1, 1,1,0,1,0, -1,1,0,0,0],
             indices=[0,1,2,2,3,0], mode='triangles', texture=texture,
             fmt=[(b'vPosition', 3, 'float'), (b'vTexCoords0', 2, 'float')])

    def _draw_label_mesh_small(self, texture=None):
        Mesh(vertices=[-0.35,-0.35,0,0,1,  0.35,-0.35,0,1,1,  0.35,0.35,0,1,0, -0.35,0.35,0,0,0],
             indices=[0,1,2,2,3,0], mode='triangles', texture=texture,
             fmt=[(b'vPosition', 3, 'float'), (b'vTexCoords0', 2, 'float')])

    def _draw_circle_mesh(self, radius=0.4):
        segments = 16
        vertices = [0, 0, 0, 0.5, 0.5]
        indices = []
        for i in range(segments + 1):
            angle = 2 * math.pi * i / segments
            vx = radius * math.cos(angle)
            vy = radius * math.sin(angle)
            u = 0.5 + 0.5 * math.cos(angle)
            v = 0.5 + 0.5 * math.sin(angle)
            vertices.extend([vx, vy, 0, u, v])
            if i > 0:
                indices.extend([0, i, i + 1])
        Mesh(vertices=vertices, indices=indices, mode='triangles',
             fmt=[(b'vPosition', 3, 'float'), (b'vTexCoords0', 2, 'float')])

    def find_clicked_cubie_robust(self, touch):
        try:
            width = self.width if self.width > 100 else 800
            height = self.height if self.height > 100 else 600
            asp = width / float(height)
            
            click_x = (touch.x / width - 0.5) * (self.zoom_scale * 2.0)
            click_y = (touch.y / height - 0.5) * (self.zoom_scale * 2.0)
            if asp > 1.0: click_x *= asp
            else: click_y /= asp

            ax = math.radians(self.angle_x)
            ay = math.radians(self.angle_y)
            best_num = None
            max_depth_z = -99999.0
            min_hit_distance = 1.35 

            for cubie in self.cubie_list:
                cx, cy, cz = cubie['x'], cubie['y'], cubie['z']
                p_face = self.determine_primary_face(cx, cy, cz)
                norm = (0, 0, 0)
                if p_face == 'FRONT':  norm = (0, 0, 1)
                elif p_face == 'BACK':  norm = (0, 0, -1)
                elif p_face == 'RIGHT': norm = (1, 0, 0)
                elif p_face == 'LEFT':  norm = (-1, 0, -1)
                elif p_face == 'TOP':   norm = (0, 1, 0)
                elif p_face == 'BOTTOM': norm = (0, -1, 0)

                orig_x = cx * 2.2 + norm[0] * 1.0
                orig_y = cy * 2.2 + norm[1] * 1.0
                orig_z = cz * 2.2 + norm[2] * 1.0

                x1 = orig_x * math.cos(ay) + orig_z * math.sin(ay)
                y1 = orig_y
                z1 = -orig_x * math.sin(ay) + orig_z * math.cos(ay)

                rot_x = x1
                rot_y = y1 * math.cos(ax) - z1 * math.sin(ax)
                rot_z = y1 * math.sin(ax) + z1 * math.cos(ax)

                nz1 = -norm[0] * math.sin(ay) + norm[2] * math.cos(ay)
                rot_nz = norm[1] * math.sin(ax) + nz1 * math.cos(ax)
                if rot_nz <= 0.15: continue

                dist_2d = math.sqrt((click_x - rot_x)**2 + (click_y - rot_y)**2)
                if dist_2d < min_hit_distance:
                    if rot_z > max_depth_z:
                        max_depth_z = rot_z
                        best_num = cubie['num']
            return best_num
        except: return None

    def on_touch_down(self, touch):
        self.idle_time = 0.0
        if not self.collide_point(*touch.pos): return False
        self.current_touches[touch.id] = touch
        if len(self.current_touches) == 2:
            self.is_moving = True 
            t_list = list(self.current_touches.values())
            self.touch_start_dist = math.sqrt((t_list[0].x - t_list[1].x)**2 + (t_list[0].y - t_list[1].y)**2)
            return True
            
        self.is_moving = False
        self.touch_start_x = touch.x
        self.touch_start_y = touch.y
        super().on_touch_down(touch)
        return True

    def on_touch_move(self, touch):
        self.idle_time = 0.0
        if touch.id not in self.current_touches: return False
        if len(self.current_touches) == 2:
            t_list = list(self.current_touches.values())
            current_dist = math.sqrt((t_list[0].x - t_list[1].x)**2 + (t_list[0].y - t_list[1].y)**2)
            if self.touch_start_dist > 0:
                factor = (self.touch_start_dist - current_dist) * 0.03
                self.zoom_scale = max(self.min_zoom, min(self.max_zoom, self.zoom_scale + factor))
                self.touch_start_dist = current_dist
            return True

        if abs(touch.x - self.touch_start_x) > 15.0 or abs(touch.y - self.touch_start_y) > 15.0:
            self.is_moving = True
            invert_y = 1.0 if math.cos(math.radians(self.angle_x)) >= 0 else -1.0
            self.angle_y += touch.dx * 0.3 * invert_y
            self.angle_x += touch.dy * 0.3
            self.angle_x = max(-85, min(85, self.angle_x))
            return True
        return super().on_touch_move(touch)

    def on_touch_up(self, touch):
        self.idle_time = 0.0
        if touch.id in self.current_touches: del self.current_touches[touch.id]
        else: return False
        if len(self.current_touches) >= 1:
            self.touch_start_dist = 0
            return True
        if self.just_zoomed:
            self.just_zoomed = False
            return True

        if not self.is_moving:
            clicked_num = self.find_clicked_cubie_robust(touch)
            if clicked_num is not None:
                if self.active_cubie is not None and self.active_cubie != clicked_num:
                    self.anim_val = 0.0 
                    self.play_sound("close")
                self.active_cubie = clicked_num
                self.play_sound("open") 
                self.open_cubie_note_ui(clicked_num)
            else:
                if touch.is_double_tap: self.open_global_note_ui()
                    
        super().on_touch_up(touch)
        return True

    def open_system_file(self, full_path):
        if not os.path.exists(full_path): return
        try:
            if sys.platform == 'win32': os.startfile(full_path)
            elif sys.platform == 'darwin': subprocess.Popen(['open', full_path])
            else: subprocess.Popen(['xdg-open', full_path])
        except: pass

    def open_file_context_menu(self, c_num, file_entry, btn_widget, file_list_layout):
        menu_layout = BoxLayout(orientation='vertical', padding=15, spacing=15)
        menu_layout.add_widget(Label(
            text=f"Bạn muốn gỡ file này khỏi ngăn chứ?\n👉 {file_entry['name']}",
            font_size='16sp', halign='center', size_hint_y=None, height=50
        ))

        def confirm_remove(btn):
            key_str = str(c_num)
            if key_str in self.data_storage["cubie_files"]:
                if file_entry in self.data_storage["cubie_files"][key_str]:
                    self.data_storage["cubie_files"][key_str].remove(file_entry)
                file_list_layout.remove_widget(btn_widget)
                self.save_to_json()
            context_popup.dismiss()

        btns_row = BoxLayout(size_hint_y=None, height=45, spacing=10)
        btn_no = Button(text="HỦY", bold=True, on_release=lambda b: context_popup.dismiss())
        btn_yes = Button(text="GỠ BỎ FILE", bold=True, background_color=(0.8, 0.1, 0.1, 1), on_release=confirm_remove)
        
        btns_row.add_widget(btn_no)
        btns_row.add_widget(btn_yes)
        menu_layout.add_widget(btns_row)

        context_popup = Popup(title="CẢNH BÁO QUẢN LÝ TÀI NGUYÊN", content=menu_layout, size_hint=(0.7, 0.35))
        context_popup.open()
    def build_file_button(self, c_num, f_entry, file_list_layout):
        # Tự động chuẩn hóa dữ liệu nếu f_entry bị lưu sai định dạng chuỗi ở phiên bản cũ
        if isinstance(f_entry, str):
            f_entry = {"name": os.path.basename(f_entry), "path": f_entry}
            
        f_name = f_entry.get("name", "Unknown File")
        f_path = f_entry.get("path", "")
        
        # Cắt ngắn tên hiển thị nếu quá dài để giao diện đẹp hơn
        display_name = f_name if len(f_name) <= 20 else f_name[:17] + "..."
        
        # TRẠNG THÁI MẶC ĐỊNH: Chữ kích thước bình thường (15sp), không in đậm
        btn = Button(
            text=display_name,
            size_hint_y=None,
            height=40,
            font_size='15sp',
            bold=False,
            background_color=(0.2, 0.2, 0.2, 1),
            color=(1, 1, 1, 1), # Chữ màu trắng bình thường
            halign='left',
            valign='middle'
        )
        btn.bind(size=btn.setter('text_size'))
        
        # --- KHỐI LỆNH XỬ LÝ HIỆU ỨNG HOVER DI CHUỘT CHO FILE ---
        def on_window_mouse_pos(window, pos):
            try:
                # Chuyển đổi tọa độ chuột toàn màn hình sang tọa độ cục bộ của nút bấm
                local_pos = btn.to_widget(*pos)
                if btn.collide_point(*local_pos):
                    # KHI DI CHUỘT VÀO: Chữ to lên (19sp), in đậm, nổi bật xanh Cyan
                    btn.font_size = '19sp'
                    btn.bold = True
                    btn.color = (0, 1, 0.8, 1)
                    btn.background_color = (0.25, 0.25, 0.25, 1)
                else:
                    # KHI DI CHUỘT RA: Trả về trạng thái chữ bình thường
                    btn.font_size = '15sp'
                    btn.bold = False
                    btn.color = (1, 1, 1, 1)
                    btn.background_color = (0.2, 0.2, 0.2, 1)
            except Exception:
                pass
            return False

        # Đăng ký sự kiện di chuột của hệ thống với nút bấm này
        Window.bind(mouse_pos=on_window_mouse_pos)
        
        # Hàm hủy lắng nghe sự kiện hover khi widget bị hủy/xóa
        def unbind_hover(*args):
            Window.unbind(mouse_pos=on_window_mouse_pos)
        btn.bind(on_kv_post=lambda ins: btn.bind(on_release=lambda b: unbind_hover()))
        # --------------------------------------------------------

        # TÍNH NĂNG: Click chuột trái mở file mặc định (GIỮ NGUYÊN)
        def open_file(instance):
            try:
                if platform.system() == "Windows":
                    os.startfile(f_path)
                elif platform.system() == "Darwin":
                    subprocess.Popen(["open", f_path])
                else:
                    subprocess.Popen(["xdg-open", f_path])
            except Exception as e:
                print(f"Lỗi mở file: {e}")
                
        btn.bind(on_release=open_file)
        
        # TÍNH NĂNG: Click chuột phải hiển thị Popup xác nhận gỡ bỏ file đính kèm
        def on_btn_touch_down(instance, touch):
            if instance.collide_point(*touch.pos) and touch.button == 'right':
                # Tạo giao diện Popup xác nhận xóa trực tiếp để tránh lỗi thiếu hàm
                del_layout = BoxLayout(orientation='vertical', padding=15, spacing=15)
                lbl_msg = Label(
                    text=f"Bạn có chắc chắn muốn gỡ bỏ file đính kèm:\n[color=ff3333]{f_name}[/color] không?",
                    markup=True, halign='center', font_size='16sp'
                )
                del_layout.add_widget(lbl_msg)
                
                btn_box = BoxLayout(size_hint_y=None, height=45, spacing=10)
                btn_no = Button(text="HỦY BỎ", bold=True, on_release=lambda b: del_popup.dismiss())
                
                # Hàm thực hiện xóa khi người dùng chọn ĐỒNG Ý
                def confirm_delete(b):
                    key_str = str(c_num)
                    if key_str in self.data_storage["cubie_files"]:
                        # Tìm và xóa mục file ra khỏi danh sách dữ liệu json
                        lst = self.data_storage["cubie_files"][key_str]
                        to_remove = None
                        for item in lst:
                            p = item.get('path', '') if isinstance(item, dict) else item
                            if p == f_path:
                                to_remove = item
                                break
                        if to_remove:
                            lst.remove(to_remove)
                            self.save_to_json()
                    
                    # Giải phóng sự kiện hover của nút cũ trước khi dọn dẹp giao diện
                    unbind_hover()
                    del_popup.dismiss()
                    
                    # Vẽ lại danh sách file đính kèm mới sau khi xóa thành công
                    file_list_layout.clear_widgets()
                    for item in self.data_storage["cubie_files"].get(key_str, []):
                        btn_file = self.build_file_button(c_num, item, file_list_layout)
                        if btn_file is not None:
                            file_list_layout.add_widget(btn_file)

                btn_yes = Button(text="ĐỒNG Ý GỠ", bold=True, background_color=(1, 0.3, 0.3, 1), on_release=confirm_delete)
                btn_box.add_widget(btn_no)
                btn_box.add_widget(btn_yes)
                del_layout.add_widget(btn_box)
                
                del_popup = Popup(title="XÁC NHẬN GỠ TÀI LIỆU", content=del_layout, size_hint=(0.8, 0.4))
                del_popup.open()
                return True
            return False
            
        btn.bind(on_touch_down=on_btn_touch_down)
        return btn

    def open_file_chooser(self, c_num, file_list_layout):
        file_popup_layout = BoxLayout(orientation='vertical', padding=10, spacing=10)
        drive_bar = BoxLayout(size_hint_y=None, height=45, spacing=5)
        
        # BỘ LỌC AN TOÀN: Chỉ hiển thị thư mục công khai và loại trừ hoàn toàn các file hệ thống nguy hiểm của Windows
        def safe_file_filter(directory, filename):
            # Danh sách đen các file hệ thống Windows luôn bị khóa quyền truy cập
            black_list = ['pagefile.sys', 'hiberfil.sys', 'swapfile.sys', 'dumpstack.log', 'ntuser.dat']
            if filename.lower() in black_list or filename.startswith('$') or filename.startswith('.'):
                return False
            return True

        # Khởi tạo bộ chọn file với bộ lọc an toàn đã cấu hình
        file_chooser = FileChooserIconView(size_hint=(1, 0.85), filters=[safe_file_filter])
        
        # Thiết lập đường dẫn khởi tạo mặc định an toàn tuyệt đối (Thư mục cá nhân của User)
        user_home = os.path.expanduser("~")
        if os.path.exists(user_home):
            file_chooser.path = user_home
        else:
            file_chooser.path = os.path.abspath(".")

        # Tạo thanh điều hướng ổ đĩa nhanh an toàn cho hệ điều hành Windows
        if sys.platform == 'win32':
            import string
            available_drives = [f"{d}:\\" for d in string.ascii_uppercase if os.path.exists(f"{d}:\\")]
            for drive in available_drives:
                btn_drive = Button(text=drive, size_hint_x=None, width=70, bold=True)
                
                # Hàm chuyển đổi ổ đĩa bọc bảo vệ Try-Except chống sập app khi di chuyển
                def change_path(instance, d=drive):
                    try:
                        file_chooser.path = d
                    except Exception as e:
                        print(f"Không thể mở ổ đĩa {d} do giới hạn bảo mật của Windows: {e}")
                
                btn_drive.bind(on_release=change_path)
                drive_bar.add_widget(btn_drive)
            file_popup_layout.add_widget(drive_bar)

        # Hàm xử lý đính kèm file khi người dùng nhấn nút xác nhận
        def on_select_file(btn):
            try:
                selection = file_chooser.selection
                if selection:
                    chosen_file = selection[0]
                    
                    # Nếu nhấn trúng thư mục thì không xử lý đính kèm file
                    if os.path.isdir(chosen_file):
                        return
                        
                    key_str = str(c_num)
                    if key_str not in self.data_storage["cubie_files"]:
                        self.data_storage["cubie_files"][key_str] = []
                    
                    f_entry = {"name": os.path.basename(chosen_file), "path": chosen_file}
                    
                    # Kiểm tra tránh trùng lặp file trong bộ nhớ json
                    is_duplicate = any(
                        (f.get('path') == chosen_file if isinstance(f, dict) else f == chosen_file)
                        for f in self.data_storage["cubie_files"][key_str]
                    )
                    
                    if not is_duplicate:
                        self.data_storage["cubie_files"][key_str].append(f_entry)
                        self.save_to_json()
                    
                    file_popup.dismiss()
                    
                    # Làm sạch danh sách và vẽ lại giao diện bằng hàm build_file_button của bạn
                    file_list_layout.clear_widgets()
                    for item in self.data_storage["cubie_files"][key_str]:
                        entry = item if isinstance(item, dict) else {"name": os.path.basename(item), "path": item}
                        btn_file = self.build_file_button(c_num, entry, file_list_layout)
                        if btn_file is not None:
                            file_list_layout.add_widget(btn_file)
            except Exception as ex:
                print(f"Lỗi phát sinh trong quá trình chọn file: {ex}")

        # Hàm xử lý kích hoạt trực tiếp khi Nhấp đúp chuột (Double click) vào file
        def on_file_submit(chooser, selection, touch):
            if selection and not os.path.isdir(selection[0]):
                on_select_file(None)

        file_chooser.bind(on_submit=on_file_submit)

        btn_layout = BoxLayout(size_hint_y=None, height=50, spacing=10)
        btn_cancel = Button(text="HỦY BỎ", bold=True, on_release=lambda b: file_popup.dismiss())
        btn_confirm = Button(text="ĐÍNH KÈM FILE", bold=True, background_color=(0, 0.6, 0.3, 1), on_release=on_select_file)
        
        btn_layout.add_widget(btn_cancel)
        btn_layout.add_widget(btn_confirm)
        file_popup_layout.add_widget(file_chooser)
        file_popup_layout.add_widget(btn_layout)
        
        file_popup = Popup(title="HỆ THỐNG CHỌN TÀI LIỆU (NHẤP ĐÚP HOẶC CHỌN RỒI ẤN ĐÍNH KÈM)", 
                           content=file_popup_layout, size_hint=(0.95, 0.95))
        file_popup.open()

    def open_cubie_note_ui(self, c_num):
        # ... giữ nguyên như bạn gửi ...
        key_str = str(c_num)
        current_style = self.data_storage["cubie_styles"].get(key_str, "THƯỜNG")

        main_popup_layout = BoxLayout(orientation='horizontal', padding=15, spacing=15)
        left_panel = BoxLayout(orientation='vertical', spacing=10, size_hint_x=0.66)
        left_panel.add_widget(Label(text="NỘI DUNG GHI CHÚ", size_hint_y=None, height=40, bold=True, font_size='24sp'))
        
        ti = TextInput(
            text=self.data_storage["cubie_notes"].get(key_str, ""),
            multiline=True, font_size='24sp', padding=[15, 15, 15, 15],
            hint_text="Gõ văn bản tiếng Việt tại đây..."
        )
        if current_style == "NGHIÊNG" and sys.platform == 'win32':
            ti.font_name = "ariali.ttf"
        left_panel.add_widget(ti)
        
        toolbar = BoxLayout(size_hint_y=None, height=55, spacing=15)
        btn_toggle = Button(text=f"KIỂU LƯU: {current_style}", font_size='16sp', bold=True, size_hint_x=0.35)
        
        def toggle_style_click(btn):
            if "THƯỜNG" in btn.text:
                btn.text = "KIỂU LƯU: NGHIÊNG"
                if sys.platform == 'win32': ti.font_name = "ariali.ttf"
            else:
                btn.text = "KIỂU LƯU: THƯỜNG"
                ti.font_name = "Roboto"
        btn_toggle.bind(on_release=toggle_style_click)
        
        btn_rename_drawer = Button(text=f"✏️ ĐỔI TÊN NGĂN {c_num:02d}", font_size='16sp', bold=True, background_color=(0.9, 0.5, 0, 1), size_hint_x=0.35)
        btn_rename_drawer.bind(on_release=lambda b: self.open_rename_ui(c_num))
        
        btn_clear = Button(text="XÓA HẾT NOTE", font_size='16sp', bold=True, background_color=(0.8, 0.2, 0.2, 1), size_hint_x=0.3)
        btn_clear.bind(on_release=lambda b: setattr(ti, 'text', ''))
        
        toolbar.add_widget(btn_toggle)
        toolbar.add_widget(btn_rename_drawer) 
        toolbar.add_widget(btn_clear)
        left_panel.add_widget(toolbar)
        
        right_panel = BoxLayout(orientation='vertical', spacing=10, size_hint_x=0.34)
        right_panel.add_widget(Label(text="DANH SÁCH FILE (PHẢI CHUỘT ĐỂ GỠ)", size_hint_y=None, height=40, bold=True, font_size='18sp', color=(1, 0.8, 0, 1)))
        
        file_scroll = ScrollView(size_hint=(1, 1))
        file_list_layout = BoxLayout(orientation='vertical', spacing=8, size_hint_y=None)
        file_list_layout.bind(minimum_height=file_list_layout.setter('height'))
        
        attached_items = self.data_storage["cubie_files"].get(key_str, [])
        for item in attached_items:
            f_entry = item if isinstance(item, dict) else {"name": os.path.basename(item), "path": item}
            btn_file = self.build_file_button(c_num, f_entry, file_list_layout)
            file_list_layout.add_widget(btn_file)
            
        file_scroll.add_widget(file_list_layout)
        right_panel.add_widget(file_scroll)
        
        btn_add_file = Button(
            text="THÊM FILE", background_color=(0.6, 0.4, 0.2, 1), 
            bold=True, font_size='16sp', size_hint_y=None, height=55,
            on_release=lambda b: self.open_file_chooser(c_num, file_list_layout)
        )
        right_panel.add_widget(btn_add_file)
        main_popup_layout.add_widget(left_panel)
        main_popup_layout.add_widget(right_panel)

        root_container = BoxLayout(orientation='vertical', padding=10, spacing=10)
        root_container.add_widget(main_popup_layout)
        row_footer = BoxLayout(size_hint_y=None, height=60, spacing=15)
        
        def close_action(btn):
            self.active_cubie = None
            self.play_sound("close")
            pop.dismiss()

        def save_action(btn):
            self.data_storage["cubie_notes"][key_str] = ti.text
            if "NGHIÊNG" in btn_toggle.text: self.data_storage["cubie_styles"][key_str] = "NGHIÊNG"
            else: self.data_storage["cubie_styles"][key_str] = "THƯỜNG"
            self.save_to_json()
            self.active_cubie = None 
            self.play_sound("close") 
            pop.dismiss()

        btn_close = Button(text="[ ĐÓNG ]", on_release=close_action, background_color=(0.15, 0.4, 0.15, 1), font_size='20sp', bold=True)
        btn_save = Button(text="[ LƯU ]", on_release=save_action, background_color=(0, 0.5, 0.7, 1), font_size='20sp', bold=True)
        
        row_footer.add_widget(btn_close)
        row_footer.add_widget(btn_save)
        root_container.add_widget(row_footer)

        pop = Popup(title=f"QUẢN LÝ HỘC TỦ SỐ {c_num:02d}", content=root_container, size_hint=(0.95, 0.95))
        pop.open()

    def open_rename_ui(self, c_num):
        # ... giữ nguyên như bạn gửi ...
        key_str = str(c_num)
        main_layout = BoxLayout(orientation='vertical', padding=25, spacing=15)
        main_layout.add_widget(Label(text=f"ĐỔI TÊN THAY THẾ CHO NGĂN SỐ {c_num:02d}", size_hint_y=None, height=40, bold=True, font_size='24sp', color=(1, 0.8, 0, 1)))
        
        current_title = self.data_storage["cubie_titles"].get(key_str, "")
        info_text = f"Mã hộc tủ gốc: Ngăn {c_num:02d}\nNhập tên mới hiển thị ngoài chấm tròn Neon:"
        main_layout.add_widget(Label(text=info_text, size_hint_y=None, height=60, font_size='16sp', halign='center'))

        ti_single = TextInput(
            text=current_title, multiline=False, font_size='22sp',
            size_hint_y=None, height=60, padding=[15, 12, 15, 12], hint_text="Nhập tên ngăn tại đây..."
        )
        main_layout.add_widget(ti_single)

        def reset_to_default_action(btn):
            if key_str in self.data_storage["cubie_titles"]: del self.data_storage["cubie_titles"][key_str]
            self.texture_cache.clear()
            self.save_to_json()
            self.update_gl(0)
            rename_pop.dismiss()

        def save_all_sides_action(btn):
            val = ti_single.text.strip()
            if val == "":
                if key_str in self.data_storage["cubie_titles"]: del self.data_storage["cubie_titles"][key_str]
            else: self.data_storage["cubie_titles"][key_str] = val
            self.texture_cache.clear()  
            self.save_to_json()
            self.update_gl(0) 
            rename_pop.dismiss()

        footer = BoxLayout(size_hint_y=None, height=60, spacing=12)
        btn_cancel = Button(text="HỦY BỎ", background_color=(0.4, 0.4, 0.4, 1), font_size='16sp', bold=True, on_release=lambda b: rename_pop.dismiss())
        btn_reset = Button(text="❌ XOÁ TÊN (HIỆN LẠI SỐ)", background_color=(0.7, 0.1, 0.1, 1), font_size='16sp', bold=True, on_release=reset_to_default_action)
        btn_save = Button(text="LƯU TÊN MỚI", background_color=(0, 0.6, 0.3, 1), font_size='16sp', bold=True, on_release=save_all_sides_action)
        
        footer.add_widget(btn_cancel)
        footer.add_widget(btn_reset)
        footer.add_widget(btn_save)
        main_layout.add_widget(footer)
        
        rename_pop = Popup(title="QUẢN LÝ TÊN NGĂN", content=main_layout, size_hint=(0.85, 0.55))
        rename_pop.open()

    def open_face_image_chooser(self, face_name, label_status, btn_action):
        popup_layout = BoxLayout(orientation='vertical', padding=10, spacing=10)
        drive_bar = BoxLayout(size_hint_y=None, height=45, spacing=5)
        img_filter = lambda folder, filename: filename.lower().endswith(('.png', '.jpg', '.jpeg', '.bmp'))
        file_chooser = FileChooserIconView(size_hint=(1, 0.85), filters=[img_filter])
        
        if sys.platform == 'win32':
            file_chooser.path = "C:\\"
            import string
            available_drives = [f"{d}:\\" for d in string.ascii_uppercase if os.path.exists(f"{d}:\\")]
            for drive in available_drives:
                btn_drive = Button(text=drive, size_hint_x=None, width=70, bold=True)
                btn_drive.bind(on_release=lambda b, d=drive: setattr(file_chooser, 'path', d))
                drive_bar.add_widget(btn_drive)
            popup_layout.add_widget(drive_bar)
        else:
            file_chooser.path = "/"

        def select_image_action(btn):
            if file_chooser.selection:
                full_path = file_chooser.selection[0]
                self.data_storage["face_images"][face_name] = full_path
                label_status.text = f"Mặt {face_name}: {os.path.basename(full_path)}"
                label_status.color = (0, 1, 0, 1)
                
                btn_action.text = "Xóa Ảnh"
                btn_action.background_color = (0.8, 0.2, 0.2, 1)
                
                if face_name in self.face_texture_cache:
                    del self.face_texture_cache[face_name]
                self.save_to_json()
            img_popup.dismiss()

        btn_layout = BoxLayout(size_hint_y=None, height=50, spacing=10)
        btn_cancel = Button(text="HỦY", bold=True, on_release=lambda b: img_popup.dismiss())
        btn_confirm = Button(text="CHỌN ẢNH NÀY", bold=True, background_color=(0, 0.6, 0.3, 1), on_release=select_image_action)
        
        btn_layout.add_widget(btn_cancel)
        btn_layout.add_widget(btn_confirm)
        popup_layout.add_widget(file_chooser)
        popup_layout.add_widget(btn_layout)
        img_popup = Popup(title=f"CHỌN ẢNH CHO MẶT {face_name}", content=popup_layout, size_hint=(0.9, 0.9))
        img_popup.open()

    def open_global_note_ui(self):
        cont = BoxLayout(orientation='vertical', padding=15, spacing=10)
        cont.add_widget(Label(text="NOTE CHUNG & CẤU HÌNH ẢNH NỀN", size_hint_y=None, height=35, bold=True, font_size='22sp'))
        
        ti = TextInput(
            text=self.data_storage.get("global_notes", ""),
            multiline=True, font_size='20sp', hint_text="Gõ ghi chú tự do toàn hệ thống tại đây...", size_hint_y=0.4
        )
        cont.add_widget(ti)
        cont.add_widget(Label(text="CÀI ĐẶT ẢNH NỀN CHO 6 MẶT RUBIK", size_hint_y=None, height=30, bold=True, font_size='18sp', color=(1, 0.8, 0, 1)))
        
        grid_faces = GridLayout(cols=2, spacing=10, size_hint_y=0.5)
        faces = ['FRONT', 'BACK', 'RIGHT', 'LEFT', 'TOP', 'BOTTOM']
        
        for f_name in faces:
            row = BoxLayout(orientation='horizontal', spacing=10)
            current_path = self.data_storage["face_images"].get(f_name, "")
            
            lbl_status = Label(
                text=f"Mặt {f_name}: " + (os.path.basename(current_path) if current_path else "Màu mặc định"),
                font_size='14sp', color=((0, 1, 0, 1) if current_path else (0.7, 0.7, 0.7, 1)),
                halign='left', valign='middle'
            )
            lbl_status.bind(size=lbl_status.setter('text_size'))
            
            btn_choose = Button(size_hint_x=None, width=120, bold=True)
            if current_path:
                btn_choose.text = "Xóa Ảnh"
                btn_choose.background_color = (0.8, 0.2, 0.2, 1)
            else:
                btn_choose.text = "Chọn Ảnh"
                btn_choose.background_color = (1, 1, 1, 1)

            def on_btn_action_release(instance, name=f_name, status_lbl=lbl_status):
                if instance.text == "Chọn Ảnh":
                    self.open_face_image_chooser(name, status_lbl, instance)
                else:
                    self.data_storage["face_images"][name] = ""
                    status_lbl.text = f"Mặt {name}: Màu mặc định"
                    status_lbl.color = (0.7, 0.7, 0.7, 1)
                    instance.text = "Chọn Ảnh"
                    instance.background_color = (1, 1, 1, 1)
                    
                    if name in self.face_texture_cache:
                        del self.face_texture_cache[name]
                    self.save_to_json()

            btn_choose.bind(on_release=on_btn_action_release)
            row.add_widget(lbl_status)
            row.add_widget(btn_choose)
            grid_faces.add_widget(row)
            
        cont.add_widget(grid_faces)
        
        def save_global_note(btn):
            self.data_storage["global_notes"] = ti.text
            self.save_to_json()
            pop.dismiss()
            
        cont.add_widget(Button(text="LƯU CẤU HÌNH HỆ THỐNG", on_release=save_global_note, size_hint_y=None, height=55, font_size='20sp', background_color=(0.1, 0.6, 0.4, 1), bold=True))
        pop = Popup(title="GHI CHÚ HỆ THỐNG & CONFIG MẶT ẢNH", content=cont, size_hint=(0.95, 0.95))
        pop.open()

    def save_to_json(self):
        data_file_path = get_data_path("rubik_data.json")
        try:
            with open(data_file_path, 'w', encoding='utf-8') as f:
                json.dump(self.data_storage, f, indent=4)
        except Exception as e:
            print(f"Lỗi hệ thống ghi dữ liệu JSON: {e}")

class RubikApp(App):
    def build(self):
        Window.clearcolor = (0, 0, 0.1, 1)
        self.bg_music = None
        bg_music_path = resource_path('background_music.mp3')
        try:
            if os.path.exists(bg_music_path):
                self.bg_music = SoundLoader.load(bg_music_path)
                if self.bg_music:
                    self.bg_music.loop = True      
                    self.bg_music.play()
        except: pass
        return RubikWidget()


if __name__ == "__main__":
    RubikApp().run()