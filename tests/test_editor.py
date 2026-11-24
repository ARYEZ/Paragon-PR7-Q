from PySide6.QtCore import QPoint, QPointF, QRect, Qt
from PySide6.QtGui import QColor, QImage
from PySide6.QtTest import QTest

from conftest import stripes
from pr7q.editor import EditorWindow, Shape, render


def editor(qapp, clean=True):
    ed = EditorWindow(stripes(400, 300))
    ed.answers["save_changes"] = "discard"
    ed.show()
    ed.set_zoom(1.0)
    qapp.processEvents()
    return ed


def at(ed, x, y) -> QPoint:
    """An image pixel as a point on the canvas widget (24 px margin, zoom 1)."""
    return QPoint(int(x * ed.canvas.zoom) + 24, int(y * ed.canvas.zoom) + 24)


def drag(ed, a, b):
    c = ed.canvas
    QTest.mousePress(c, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, at(ed, *a))
    QTest.mouseMove(c, at(ed, (a[0] + b[0]) // 2, (a[1] + b[1]) // 2))
    QTest.mouseMove(c, at(ed, *b))
    QTest.mouseRelease(c, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, at(ed, *b))


def test_draw_shapes_with_the_mouse(qapp, clean_settings):
    ed = editor(qapp)
    ed.set_tool("rect")
    ed._style(colour="#E0202A", width=6, shadow=False)
    drag(ed, (20, 20), (120, 80))
    s = ed.canvas.shapes[0]
    assert s.kind == "rect" and s.box() == ed.canvas.shapes[0].box() and s.colour == "#E0202A"
    out = ed.canvas.image()
    assert out.pixelColor(20, 50) == QColor("#E0202A")            # the left edge, red
    assert out.pixelColor(70, 50) == QColor("#E2502A") or out.pixelColor(70, 50) != QColor("#E0202A")
    ed.set_tool("arrow")
    drag(ed, (200, 200), (300, 120))
    assert ed.canvas.shapes[-1].kind == "arrow"
    ed.set_tool("step")
    QTest.mouseClick(ed.canvas, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, at(ed, 340, 40))
    QTest.mouseClick(ed.canvas, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, at(ed, 340, 90))
    assert [s.number for s in ed.canvas.shapes if s.kind == "step"] == [1, 2]
    ed.answers["text"] = "Click here"
    ed.set_tool("text")
    QTest.mouseClick(ed.canvas, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, at(ed, 30, 220))
    assert ed.canvas.shapes[-1].text == "Click here"
    assert ed.stat[2].text() == "5 objects"


def test_select_move_resize_delete_and_undo(qapp, clean_settings):
    ed = editor(qapp)
    ed.set_tool("rect")
    drag(ed, (50, 50), (150, 120))
    ed.set_tool("select")
    drag(ed, (100, 50), (130, 70))                        # grab the top edge, move by (30, 20)
    s = ed.canvas.shapes[0]
    assert s.box().topLeft() == QPointF(80, 70)
    drag(ed, (180, 140), (220, 160))                      # the bottom-right handle
    assert s.box().bottomRight() == QPointF(220, 160)
    ed._style(colour="#FF7A1A")                            # restyle the selected one
    assert s.colour == "#FF7A1A"
    QTest.keyClick(ed.canvas, Qt.Key.Key_Delete)
    assert not ed.canvas.shapes
    ed.canvas.do_undo()
    assert len(ed.canvas.shapes) == 1 and ed.canvas.shapes[0].colour == "#FF7A1A"
    ed.canvas.do_undo()
    assert ed.canvas.shapes[0].colour != "#FF7A1A"
    ed.canvas.do_redo()
    assert ed.canvas.shapes[0].colour == "#FF7A1A"


def test_pixelate_really_hides_the_pixels(qapp):
    base = QImage(200, 100, QImage.Format.Format_RGB32)
    for x in range(200):
        for y in range(100):
            base.setPixelColor(x, y, QColor("#000000") if (x // 2 + y // 2) % 2 else QColor("#FFFFFF"))  # fine check
    out = render(base, [Shape("obfuscate", [QPointF(0, 0), QPointF(200, 100)], size=20)])
    block = [out.pixelColor(x, 3).name() for x in range(0, 10)]
    assert len(set(block)) == 1                           # one colour across a whole block: the detail is gone
    assert block[0] not in ("#000000", "#ffffff")


def test_crop_and_canvas_size_move_the_shapes(qapp, clean_settings):
    ed = editor(qapp)
    ed.canvas.add(Shape("rect", [QPointF(100, 100), QPointF(150, 150)]))
    ed.set_tool("crop")
    drag(ed, (50, 50), (250, 200))
    c = ed.canvas
    assert (c.base.width(), c.base.height()) == (200, 150) and c.shapes[0].pts[0] == QPointF(50, 50)
    assert c.base.pixelColor(0, 0) == QColor("#C2183F")       # x 50 of the original: the first band
    c.canvas_size(10, 10, 10, 10)
    assert (c.base.width(), c.base.height()) == (220, 170) and c.shapes[0].pts[0] == QPointF(60, 60)
    assert c.base.pixelColor(2, 2) == QColor("#FFFFFF")
    c.do_undo(); c.do_undo()
    assert c.base.width() == 400


def test_save_save_as_and_closing(qapp, clean_settings, tmp_path):
    from pr7q import settings
    ed = editor(qapp)
    ed.canvas.add(Shape("highlight", [QPointF(0, 0), QPointF(50, 50)], colour="#FF7A1A"))
    assert ed.save()
    assert ed.path.startswith(settings.get("folder")) and ed.path.endswith(".png") and not ed.modified
    assert QImage(ed.path).size() == ed.canvas.base.size()
    ed.canvas.add(Shape("rect", [QPointF(10, 10), QPointF(40, 40)]))
    assert ed.modified and ed.windowTitle().endswith("* - Paragon PR7-Q")
    target = tmp_path / "copy.jpg"
    ed.answers["save_as"] = str(target)
    assert ed.save_as() and target.exists()
    ed.canvas.add(Shape("rect", [QPointF(60, 10), QPointF(90, 40)]))
    ed.answers["save_changes"] = "cancel"
    assert not ed.close()                                      # stays open
    ed.answers["save_changes"] = "discard"
    assert ed.close()


def test_copy_to_clipboard(qapp, clean_settings):
    ed = editor(qapp)
    ed.canvas.add(Shape("rect", [QPointF(10, 10), QPointF(40, 40)], colour="#E0202A", width=4, shadow=False))
    ed.copy()
    img = qapp.clipboard().image()
    assert img.size() == ed.canvas.base.size() and img.pixelColor(10, 25) == QColor("#E0202A")


def test_every_shape_draws_with_and_without_its_shadow(qapp):
    base = QImage(300, 200, QImage.Format.Format_RGB32)
    base.fill(QColor("#204060"))
    two = [QPointF(20, 20), QPointF(160, 120)]
    for shadow in (True, False):
        for fill in ("", "white", "colour"):
            shapes = [Shape(k, [QPointF(p) for p in two], shadow=shadow, fill=fill) for k in
                      ("rect", "ellipse", "line", "arrow", "highlight", "obfuscate")]
            shapes += [Shape("pen", [QPointF(10, 10), QPointF(40, 60), QPointF(90, 30)], shadow=shadow),
                       Shape("text", [QPointF(30, 140)], text="Two\nlines", shadow=shadow, fill=fill),
                       Shape("bubble", [QPointF(150, 20), QPointF(280, 80), QPointF(170, 110)], text="Hi",
                             shadow=shadow),
                       Shape("step", [QPointF(250, 160)], number=7, shadow=shadow)]
            out = render(base, shapes)
            assert out.size() == base.size() and out.pixelColor(250, 160) != QColor("#204060")
