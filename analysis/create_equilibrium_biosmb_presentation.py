"""Create a five-slide PowerPoint update for the pH modeling project.

The script uses only the Python standard library. It writes a small Office Open
XML PowerPoint deck so the presentation can be regenerated without adding
python-pptx as a project dependency.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from html import escape
import struct
from pathlib import Path
from typing import Iterable
from zipfile import ZIP_DEFLATED, ZipFile


EMU_PER_INCH = 914400
SLIDE_W = 12192000
SLIDE_H = 6858000

REPO_ROOT = Path(__file__).resolve().parents[1]
OUTPUT = REPO_ROOT / "reports" / "presentations" / "equilibrium_biosmb_experiment_update.pptx"

EQUILIBRIUM_SCATTER = (
    REPO_ROOT
    / "results"
    / "equilibrium_main_model_20260525_213424"
    / "figures"
    / "lab_equilibrium_validation_scatter.png"
)
BIOSMB_PLUMBING_MAP = (
    REPO_ROOT
    / "results"
    / "biosmb_ph_plumbing_map_20260528_021943"
    / "figures"
    / "biosmb_ph_plumbing_map.png"
)


COLORS = {
    "maroon": "7A263A",
    "ink": "202A36",
    "muted": "64748B",
    "teal": "0F9A9B",
    "blue": "357ABD",
    "green": "2C8A5A",
    "red": "B72418",
    "gold": "D79B20",
    "bg": "F8FAFC",
    "panel": "FFFFFF",
    "line": "D7DEE8",
    "soft_teal": "DDF3F2",
    "soft_red": "F8E4E1",
    "soft_green": "E7F3EC",
    "soft_gold": "FFF1CC",
    "soft_blue": "E6EEF8",
}


def emu(inches: float) -> int:
    return int(round(inches * EMU_PER_INCH))


def xesc(text: str) -> str:
    return escape(str(text), quote=True)


def xml_timestamp() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def png_size(path: Path) -> tuple[int, int]:
    with path.open("rb") as handle:
        signature = handle.read(8)
        if signature != b"\x89PNG\r\n\x1a\n":
            raise ValueError(f"Not a PNG file: {path}")
        length = struct.unpack(">I", handle.read(4))[0]
        chunk_type = handle.read(4)
        if length != 13 or chunk_type != b"IHDR":
            raise ValueError(f"PNG has no expected IHDR chunk: {path}")
        width, height = struct.unpack(">II", handle.read(8))
    return width, height


@dataclass
class Shape:
    xml: str


@dataclass
class ImageRel:
    path: Path
    media_name: str
    rel_id: str


@dataclass
class Slide:
    title: str
    shapes: list[Shape] = field(default_factory=list)
    images: list[ImageRel] = field(default_factory=list)
    _shape_id: int = 2

    def next_id(self) -> int:
        self._shape_id += 1
        return self._shape_id

    def add_shape_xml(self, xml: str) -> None:
        self.shapes.append(Shape(xml))

    def add_background(self) -> None:
        self.add_shape_xml(rect_xml(self.next_id(), 0, 0, SLIDE_W, SLIDE_H, COLORS["bg"], COLORS["bg"]))
        self.add_shape_xml(rect_xml(self.next_id(), 0, 0, SLIDE_W, emu(0.16), COLORS["maroon"], COLORS["maroon"]))

    def add_title(self, text: str, kicker: str | None = None) -> None:
        if kicker:
            self.add_shape_xml(
                text_box_xml(
                    self.next_id(),
                    emu(0.48),
                    emu(0.32),
                    emu(11.9),
                    emu(0.28),
                    [(kicker.upper(), 11, COLORS["maroon"], True, False)],
                )
            )
            title_y = emu(0.56)
        else:
            title_y = emu(0.36)
        self.add_shape_xml(
            text_box_xml(
                self.next_id(),
                emu(0.48),
                title_y,
                emu(12.0),
                emu(0.55),
                [(text, 28, COLORS["ink"], True, False)],
            )
        )

    def add_footer(self, idx: int) -> None:
        self.add_shape_xml(
            text_box_xml(
                self.next_id(),
                emu(0.48),
                emu(7.13),
                emu(10.6),
                emu(0.22),
                [
                    (
                        "pH modeling update | equilibrium chemistry, BioSMB library, and open-loop experiments",
                        7.5,
                        COLORS["muted"],
                        False,
                        False,
                    )
                ],
            )
        )
        self.add_shape_xml(
            text_box_xml(
                self.next_id(),
                emu(12.22),
                emu(7.13),
                emu(0.9),
                emu(0.22),
                [(f"{idx}/5", 7.5, COLORS["muted"], False, False)],
                align="r",
            )
        )


def solid_fill(color: str) -> str:
    return f'<a:solidFill><a:srgbClr val="{color}"/></a:solidFill>'


def line_xml(color: str = "FFFFFF", width: int = 10000, no_line: bool = False) -> str:
    if no_line:
        return "<a:ln><a:noFill/></a:ln>"
    return f'<a:ln w="{width}">{solid_fill(color)}</a:ln>'


def rect_xml(
    shape_id: int,
    x: int,
    y: int,
    w: int,
    h: int,
    fill: str,
    line: str,
    radius: str = "roundRect",
) -> str:
    return f"""
<p:sp>
  <p:nvSpPr>
    <p:cNvPr id="{shape_id}" name="Shape {shape_id}"/>
    <p:cNvSpPr/>
    <p:nvPr/>
  </p:nvSpPr>
  <p:spPr>
    <a:xfrm><a:off x="{x}" y="{y}"/><a:ext cx="{w}" cy="{h}"/></a:xfrm>
    <a:prstGeom prst="{radius}"><a:avLst/></a:prstGeom>
    {solid_fill(fill)}
    {line_xml(line)}
  </p:spPr>
</p:sp>"""


def paragraph_xml(
    text: str,
    size: float,
    color: str,
    bold: bool,
    bullet: bool,
    align: str = "l",
    space_after: int = 0,
) -> str:
    bullet_xml = ""
    if bullet:
        bullet_xml = '<a:buChar char="&#8226;"/>'
        ppr = f'<a:pPr marL="285750" indent="-171450" algn="{align}" spcAft="{space_after}">{bullet_xml}</a:pPr>'
    else:
        ppr = f'<a:pPr algn="{align}" spcAft="{space_after}"/>'
    bold_attr = ' b="1"' if bold else ""
    sz = int(round(size * 100))
    return f"""
<a:p>
  {ppr}
  <a:r>
    <a:rPr lang="en-US" sz="{sz}"{bold_attr}>
      {solid_fill(color)}
      <a:latin typeface="Aptos"/>
    </a:rPr>
    <a:t>{xesc(text)}</a:t>
  </a:r>
</a:p>"""


def text_box_xml(
    shape_id: int,
    x: int,
    y: int,
    w: int,
    h: int,
    lines: Iterable[tuple[str, float, str, bool, bool]],
    align: str = "l",
    fill: str | None = None,
    border: str | None = None,
    radius: str = "rect",
    margin: int = 76000,
) -> str:
    fill_xml = "<a:noFill/>" if fill is None else solid_fill(fill)
    border_xml = line_xml(no_line=True) if border is None else line_xml(border, width=8500)
    paragraph_list = [
        paragraph_xml(text, size, color, bold, bullet, align=align, space_after=20000)
        for text, size, color, bold, bullet in lines
    ]
    body = "".join(paragraph_list)
    return f"""
<p:sp>
  <p:nvSpPr>
    <p:cNvPr id="{shape_id}" name="TextBox {shape_id}"/>
    <p:cNvSpPr txBox="1"/>
    <p:nvPr/>
  </p:nvSpPr>
  <p:spPr>
    <a:xfrm><a:off x="{x}" y="{y}"/><a:ext cx="{w}" cy="{h}"/></a:xfrm>
    <a:prstGeom prst="{radius}"><a:avLst/></a:prstGeom>
    {fill_xml}
    {border_xml}
  </p:spPr>
  <p:txBody>
    <a:bodyPr wrap="square" lIns="{margin}" rIns="{margin}" tIns="{margin}" bIns="{margin}"/>
    <a:lstStyle/>
    {body}
  </p:txBody>
</p:sp>"""


def image_xml(shape_id: int, rel_id: str, x: int, y: int, w: int, h: int) -> str:
    return f"""
<p:pic>
  <p:nvPicPr>
    <p:cNvPr id="{shape_id}" name="Picture {shape_id}"/>
    <p:cNvPicPr><a:picLocks noChangeAspect="1"/></p:cNvPicPr>
    <p:nvPr/>
  </p:nvPicPr>
  <p:blipFill>
    <a:blip r:embed="{rel_id}"/>
    <a:stretch><a:fillRect/></a:stretch>
  </p:blipFill>
  <p:spPr>
    <a:xfrm><a:off x="{x}" y="{y}"/><a:ext cx="{w}" cy="{h}"/></a:xfrm>
    <a:prstGeom prst="rect"><a:avLst/></a:prstGeom>
  </p:spPr>
</p:pic>"""


def add_fit_image(slide: Slide, path: Path, x: float, y: float, w: float, h: float, media_idx: int) -> int:
    px_w, px_h = png_size(path)
    box_w = emu(w)
    box_h = emu(h)
    ratio = min(box_w / px_w, box_h / px_h)
    draw_w = int(px_w * ratio)
    draw_h = int(px_h * ratio)
    draw_x = emu(x) + (box_w - draw_w) // 2
    draw_y = emu(y) + (box_h - draw_h) // 2
    rel_id = f"rId{len(slide.images) + 2}"
    media_name = f"image{media_idx}.png"
    slide.images.append(ImageRel(path=path, media_name=media_name, rel_id=rel_id))
    slide.add_shape_xml(image_xml(slide.next_id(), rel_id, draw_x, draw_y, draw_w, draw_h))
    return media_idx + 1


def add_panel(
    slide: Slide,
    x: float,
    y: float,
    w: float,
    h: float,
    title: str,
    lines: list[str],
    color: str,
    fill: str = "FFFFFF",
    title_size: float = 13,
    body_size: float = 11,
) -> None:
    slide.add_shape_xml(rect_xml(slide.next_id(), emu(x), emu(y), emu(w), emu(h), fill, COLORS["line"]))
    slide.add_shape_xml(rect_xml(slide.next_id(), emu(x), emu(y), emu(0.08), emu(h), color, color, radius="rect"))
    text_lines: list[tuple[str, float, str, bool, bool]] = [(title, title_size, COLORS["ink"], True, False)]
    text_lines.extend((line, body_size, COLORS["ink"], False, True) for line in lines)
    slide.add_shape_xml(
        text_box_xml(
            slide.next_id(),
            emu(x + 0.12),
            emu(y + 0.06),
            emu(w - 0.2),
            emu(h - 0.1),
            text_lines,
        )
    )


def add_metric_card(slide: Slide, x: float, y: float, label: str, value: str, detail: str, fill: str, color: str) -> None:
    slide.add_shape_xml(rect_xml(slide.next_id(), emu(x), emu(y), emu(1.65), emu(0.94), fill, COLORS["line"]))
    slide.add_shape_xml(
        text_box_xml(
            slide.next_id(),
            emu(x + 0.08),
            emu(y + 0.06),
            emu(1.5),
            emu(0.82),
            [
                (label, 8.5, COLORS["muted"], True, False),
                (value, 21, color, True, False),
                (detail, 7.5, COLORS["muted"], False, False),
            ],
            margin=28000,
        )
    )


def add_simple_table(
    slide: Slide,
    x: float,
    y: float,
    widths: list[float],
    row_h: float,
    rows: list[list[str]],
    header_fill: str,
    header_color: str = "FFFFFF",
    body_fill: str = "FFFFFF",
    font_size: float = 8.5,
) -> None:
    for r_idx, row in enumerate(rows):
        cur_x = x
        for c_idx, cell in enumerate(row):
            fill = header_fill if r_idx == 0 else body_fill
            text_color = header_color if r_idx == 0 else COLORS["ink"]
            bold = r_idx == 0
            slide.add_shape_xml(
                rect_xml(
                    slide.next_id(),
                    emu(cur_x),
                    emu(y + r_idx * row_h),
                    emu(widths[c_idx]),
                    emu(row_h),
                    fill,
                    COLORS["line"],
                    radius="rect",
                )
            )
            slide.add_shape_xml(
                text_box_xml(
                    slide.next_id(),
                    emu(cur_x + 0.03),
                    emu(y + r_idx * row_h + 0.02),
                    emu(widths[c_idx] - 0.06),
                    emu(row_h - 0.04),
                    [(cell, font_size, text_color, bold, False)],
                    align="c" if c_idx > 0 else "l",
                    margin=18000,
                )
            )
            cur_x += widths[c_idx]


def connector_line(shape_id: int, x1: float, y1: float, x2: float, y2: float, color: str) -> str:
    x1e, y1e, x2e, y2e = emu(x1), emu(y1), emu(x2), emu(y2)
    return f"""
<p:cxnSp>
  <p:nvCxnSpPr>
    <p:cNvPr id="{shape_id}" name="Connector {shape_id}"/>
    <p:cNvCxnSpPr/>
    <p:nvPr/>
  </p:nvCxnSpPr>
  <p:spPr>
    <a:xfrm><a:off x="{min(x1e, x2e)}" y="{min(y1e, y2e)}"/><a:ext cx="{abs(x2e - x1e)}" cy="{abs(y2e - y1e)}"/></a:xfrm>
    <a:prstGeom prst="line"><a:avLst/></a:prstGeom>
    <a:ln w="18000">{solid_fill(color)}<a:tailEnd type="none"/><a:headEnd type="triangle"/></a:ln>
  </p:spPr>
</p:cxnSp>"""


def slide_xml(slide: Slide) -> str:
    body = "\n".join(shape.xml for shape in slide.shapes)
    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:sld xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"
       xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"
       xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main">
  <p:cSld>
    <p:spTree>
      <p:nvGrpSpPr>
        <p:cNvPr id="1" name=""/>
        <p:cNvGrpSpPr/>
        <p:nvPr/>
      </p:nvGrpSpPr>
      <p:grpSpPr>
        <a:xfrm>
          <a:off x="0" y="0"/><a:ext cx="{SLIDE_W}" cy="{SLIDE_H}"/>
          <a:chOff x="0" y="0"/><a:chExt cx="{SLIDE_W}" cy="{SLIDE_H}"/>
        </a:xfrm>
      </p:grpSpPr>
      {body}
    </p:spTree>
  </p:cSld>
  <p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr>
</p:sld>"""


def slide_rels_xml(slide: Slide) -> str:
    rels = [
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideLayout" Target="../slideLayouts/slideLayout1.xml"/>'
    ]
    for image in slide.images:
        rels.append(
            f'<Relationship Id="{image.rel_id}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" Target="../media/{image.media_name}"/>'
        )
    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  {"".join(rels)}
</Relationships>"""


def content_types_xml(slides: list[Slide]) -> str:
    slide_overrides = "\n".join(
        f'<Override PartName="/ppt/slides/slide{i}.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slide+xml"/>'
        for i in range(1, len(slides) + 1)
    )
    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Default Extension="png" ContentType="image/png"/>
  <Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>
  <Override PartName="/docProps/app.xml" ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/>
  <Override PartName="/ppt/presentation.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.presentation.main+xml"/>
  <Override PartName="/ppt/slideMasters/slideMaster1.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slideMaster+xml"/>
  <Override PartName="/ppt/slideLayouts/slideLayout1.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slideLayout+xml"/>
  <Override PartName="/ppt/theme/theme1.xml" ContentType="application/vnd.openxmlformats-officedocument.theme+xml"/>
  {slide_overrides}
</Types>"""


def package_rels_xml() -> str:
    return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="ppt/presentation.xml"/>
  <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/>
  <Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties" Target="docProps/app.xml"/>
</Relationships>"""


def core_xml(created: str) -> str:
    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties"
  xmlns:dc="http://purl.org/dc/elements/1.1/"
  xmlns:dcterms="http://purl.org/dc/terms/"
  xmlns:dcmitype="http://purl.org/dc/dcmitype/"
  xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
  <dc:title>Equilibrium, BioSMB, and Open-Loop pH Experiments</dc:title>
  <dc:creator>Codex</dc:creator>
  <cp:lastModifiedBy>Codex</cp:lastModifiedBy>
  <dcterms:created xsi:type="dcterms:W3CDTF">{created}</dcterms:created>
  <dcterms:modified xsi:type="dcterms:W3CDTF">{created}</dcterms:modified>
</cp:coreProperties>"""


def app_xml(slide_count: int) -> str:
    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties"
  xmlns:vt="http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes">
  <Application>Microsoft PowerPoint</Application>
  <PresentationFormat>On-screen Show (16:9)</PresentationFormat>
  <Slides>{slide_count}</Slides>
  <Notes>0</Notes>
  <HiddenSlides>0</HiddenSlides>
  <MMClips>0</MMClips>
  <ScaleCrop>false</ScaleCrop>
  <Company>pHRLController</Company>
  <LinksUpToDate>false</LinksUpToDate>
  <SharedDoc>false</SharedDoc>
  <HyperlinksChanged>false</HyperlinksChanged>
  <AppVersion>16.0000</AppVersion>
</Properties>"""


def presentation_xml(slide_count: int) -> str:
    slide_ids = "\n".join(
        f'<p:sldId id="{255 + i}" r:id="rId{i + 1}"/>' for i in range(1, slide_count + 1)
    )
    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:presentation xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"
  xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"
  xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main">
  <p:sldMasterIdLst>
    <p:sldMasterId id="2147483648" r:id="rId1"/>
  </p:sldMasterIdLst>
  <p:sldIdLst>
    {slide_ids}
  </p:sldIdLst>
  <p:sldSz cx="{SLIDE_W}" cy="{SLIDE_H}" type="wide"/>
  <p:notesSz cx="6858000" cy="9144000"/>
</p:presentation>"""


def presentation_rels_xml(slide_count: int) -> str:
    rels = [
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideMaster" Target="slideMasters/slideMaster1.xml"/>'
    ]
    for i in range(1, slide_count + 1):
        rels.append(
            f'<Relationship Id="rId{i + 1}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slide" Target="slides/slide{i}.xml"/>'
        )
    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  {"".join(rels)}
</Relationships>"""


def theme_xml() -> str:
    return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<a:theme xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" name="pH Modeling Theme">
  <a:themeElements>
    <a:clrScheme name="pH Modeling">
      <a:dk1><a:srgbClr val="202A36"/></a:dk1>
      <a:lt1><a:srgbClr val="FFFFFF"/></a:lt1>
      <a:dk2><a:srgbClr val="334155"/></a:dk2>
      <a:lt2><a:srgbClr val="F8FAFC"/></a:lt2>
      <a:accent1><a:srgbClr val="7A263A"/></a:accent1>
      <a:accent2><a:srgbClr val="0F9A9B"/></a:accent2>
      <a:accent3><a:srgbClr val="2C8A5A"/></a:accent3>
      <a:accent4><a:srgbClr val="D79B20"/></a:accent4>
      <a:accent5><a:srgbClr val="357ABD"/></a:accent5>
      <a:accent6><a:srgbClr val="B72418"/></a:accent6>
      <a:hlink><a:srgbClr val="357ABD"/></a:hlink>
      <a:folHlink><a:srgbClr val="7A263A"/></a:folHlink>
    </a:clrScheme>
    <a:fontScheme name="Aptos">
      <a:majorFont><a:latin typeface="Aptos Display"/></a:majorFont>
      <a:minorFont><a:latin typeface="Aptos"/></a:minorFont>
    </a:fontScheme>
    <a:fmtScheme name="pH Modeling">
      <a:fillStyleLst><a:solidFill><a:schemeClr val="phClr"/></a:solidFill></a:fillStyleLst>
      <a:lnStyleLst><a:ln w="6350"><a:solidFill><a:schemeClr val="phClr"/></a:solidFill></a:ln></a:lnStyleLst>
      <a:effectStyleLst><a:effectStyle><a:effectLst/></a:effectStyle></a:effectStyleLst>
      <a:bgFillStyleLst><a:solidFill><a:schemeClr val="phClr"/></a:solidFill></a:bgFillStyleLst>
    </a:fmtScheme>
  </a:themeElements>
  <a:objectDefaults/>
  <a:extraClrSchemeLst/>
</a:theme>"""


def slide_master_xml() -> str:
    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:sldMaster xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"
  xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"
  xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main">
  <p:cSld>
    <p:bg><p:bgPr>{solid_fill(COLORS["bg"])}</p:bgPr></p:bg>
    <p:spTree>
      <p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr>
      <p:grpSpPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="{SLIDE_W}" cy="{SLIDE_H}"/><a:chOff x="0" y="0"/><a:chExt cx="{SLIDE_W}" cy="{SLIDE_H}"/></a:xfrm></p:grpSpPr>
    </p:spTree>
  </p:cSld>
  <p:clrMap bg1="lt1" tx1="dk1" bg2="lt2" tx2="dk2" accent1="accent1" accent2="accent2" accent3="accent3" accent4="accent4" accent5="accent5" accent6="accent6" hlink="hlink" folHlink="folHlink"/>
  <p:sldLayoutIdLst><p:sldLayoutId id="2147483649" r:id="rId1"/></p:sldLayoutIdLst>
  <p:txStyles>
    <p:titleStyle><a:lvl1pPr><a:defRPr sz="2800"/></a:lvl1pPr></p:titleStyle>
    <p:bodyStyle><a:lvl1pPr><a:defRPr sz="1800"/></a:lvl1pPr></p:bodyStyle>
    <p:otherStyle><a:lvl1pPr><a:defRPr sz="1800"/></a:lvl1pPr></p:otherStyle>
  </p:txStyles>
</p:sldMaster>"""


def slide_master_rels_xml() -> str:
    return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideLayout" Target="../slideLayouts/slideLayout1.xml"/>
  <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/theme" Target="../theme/theme1.xml"/>
</Relationships>"""


def slide_layout_xml() -> str:
    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:sldLayout xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"
  xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"
  xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main" type="blank" preserve="1">
  <p:cSld name="Blank">
    <p:spTree>
      <p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr>
      <p:grpSpPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="{SLIDE_W}" cy="{SLIDE_H}"/><a:chOff x="0" y="0"/><a:chExt cx="{SLIDE_W}" cy="{SLIDE_H}"/></a:xfrm></p:grpSpPr>
    </p:spTree>
  </p:cSld>
  <p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr>
</p:sldLayout>"""


def slide_layout_rels_xml() -> str:
    return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideMaster" Target="../slideMasters/slideMaster1.xml"/>
</Relationships>"""


def build_slides() -> list[Slide]:
    slides: list[Slide] = []
    media_idx = 1

    s1 = Slide("Equilibrium model is a calibrated chemistry core")
    s1.add_background()
    s1.add_title("Equilibrium model is a calibrated chemistry core", "equilibrium work")
    add_panel(
        s1,
        0.55,
        1.2,
        4.4,
        1.35,
        "Model role",
        [
            "Charge balance uses acid, acetate, and water flows.",
            "Raw pH_eq is a physical coordinate, not a standalone simulator.",
            "Current PH_2 map: 0.6567 + 0.7909 pH_eq.",
        ],
        COLORS["teal"],
        fill=COLORS["soft_teal"],
        body_size=10.2,
    )
    add_metric_card(s1, 0.55, 2.78, "Raw test RMSE", "0.441", "pH units", COLORS["soft_red"], COLORS["red"])
    add_metric_card(s1, 2.35, 2.78, "Affine test RMSE", "0.0975", "pH units", COLORS["soft_green"], COLORS["green"])
    add_metric_card(s1, 4.15, 2.78, "Affine max abs", "0.247", "test split", COLORS["soft_gold"], COLORS["gold"])
    add_panel(
        s1,
        0.55,
        4.05,
        4.95,
        1.42,
        "Interpretation",
        [
            "Measured PH_2 is lower and compressed relative to ideal equilibrium.",
            "The calibration is useful evidence, but dynamics are still missing.",
            "Next model should identify delay, mixing, and sensor response.",
        ],
        COLORS["maroon"],
        fill="FFFFFF",
        body_size=10.2,
    )
    media_idx = add_fit_image(s1, EQUILIBRIUM_SCATTER, 5.75, 1.23, 6.7, 4.95, media_idx)
    s1.add_shape_xml(
        text_box_xml(
            s1.next_id(),
            emu(5.85),
            emu(6.18),
            emu(6.55),
            emu(0.42),
            [("Evidence: measured PH_2 versus raw equilibrium pH, train/test split.", 9, COLORS["muted"], False, False)],
        )
    )
    s1.add_footer(1)
    slides.append(s1)

    s2 = Slide("BioSMB gives the hardware interface, not the plant model")
    s2.add_background()
    s2.add_title("BioSMB gives the hardware interface, not the plant model", "biosmb library")
    media_idx = add_fit_image(s2, BIOSMB_PLUMBING_MAP, 0.5, 1.08, 8.45, 5.55, media_idx)
    add_panel(
        s2,
        9.18,
        1.18,
        3.42,
        1.42,
        "Confirmed pH mapping",
        [
            "Pump 2: acetic acid.",
            "Pump 3: sodium acetate.",
            "Pump 4: Arium water.",
            "Reliable output: PH_2 with get_ph(2).",
        ],
        COLORS["blue"],
        fill=COLORS["soft_blue"],
        body_size=9.4,
    )
    add_panel(
        s2,
        9.18,
        2.85,
        3.42,
        1.42,
        "Library API",
        [
            "One-indexed pumps and sensors.",
            "Valve labels are column plus row, e.g. P2/P3/P4.",
            "OPC-UA wrapper reads and writes hardware nodes.",
        ],
        COLORS["teal"],
        fill=COLORS["soft_teal"],
        body_size=9.4,
    )
    add_panel(
        s2,
        9.18,
        4.52,
        3.42,
        1.24,
        "Safety gap",
        [
            "The library does not enforce flow bounds, finite schedules, or cleanup.",
            "Experiment runners must add those controls.",
        ],
        COLORS["red"],
        fill=COLORS["soft_red"],
        body_size=9.4,
    )
    s2.add_shape_xml(
        text_box_xml(
            s2.next_id(),
            emu(0.55),
            emu(6.56),
            emu(8.3),
            emu(0.34),
            [("P2/P3/P4 are valve coordinates on the pH inlet rows, not pump numbers.", 9.2, COLORS["muted"], False, False)],
        )
    )
    s2.add_footer(2)
    slides.append(s2)

    s3 = Slide("Read-only smoke test proved the library path before writes")
    s3.add_background()
    s3.add_title("Read-only smoke test proved the library path before writes", "biosmb library")
    pipeline = [
        ("Local OPC emulator", COLORS["soft_blue"], COLORS["blue"]),
        ("Temporary settings.json", COLORS["soft_gold"], COLORS["gold"]),
        ("BioSMBManager", COLORS["soft_teal"], COLORS["teal"]),
        ("Read flows, valves, PH_2, sensors", COLORS["soft_green"], COLORS["green"]),
    ]
    x0 = 0.65
    for idx, (label, fill, color) in enumerate(pipeline):
        x = x0 + idx * 3.0
        s3.add_shape_xml(rect_xml(s3.next_id(), emu(x), emu(1.45), emu(2.35), emu(0.72), fill, color))
        s3.add_shape_xml(
            text_box_xml(
                s3.next_id(),
                emu(x + 0.08),
                emu(1.52),
                emu(2.18),
                emu(0.54),
                [(label, 10.5, COLORS["ink"], True, False)],
                align="c",
                margin=24000,
            )
        )
        if idx < len(pipeline) - 1:
            s3.add_shape_xml(connector_line(s3.next_id(), x + 2.38, 1.81, x + 2.88, 1.81, COLORS["muted"]))
    add_panel(
        s3,
        0.75,
        2.75,
        5.75,
        2.08,
        "What the read-only script checks",
        [
            "Imports the real biosmb_interface and emulator packages.",
            "Connects to opc.tcp://127.0.0.1:4865/BioSMB/.",
            "Resolves P2, P3, P4 and pump readbacks for pumps 2-4.",
            "Reads current pH with biosmb.get_ph(2).",
        ],
        COLORS["teal"],
        fill="FFFFFF",
        body_size=10.2,
    )
    add_panel(
        s3,
        6.95,
        2.75,
        5.45,
        2.08,
        "What it deliberately avoids",
        [
            "No enable_pump calls.",
            "No set_flow calls.",
            "No open_valve calls.",
            "No claim that the physical outlet path is fully verified.",
        ],
        COLORS["red"],
        fill="FFFFFF",
        body_size=10.2,
    )
    add_panel(
        s3,
        0.75,
        5.28,
        11.65,
        0.78,
        "Next safe use",
        [
            "Move from emulator read-only validation to a supervised valve-only or very low-flow hardware check with try/finally cleanup.",
        ],
        COLORS["gold"],
        fill=COLORS["soft_gold"],
        body_size=10.8,
    )
    s3.add_footer(3)
    slides.append(s3)

    s4 = Slide("Experiment 1 should step pH chemistry at fixed total flow")
    s4.add_background()
    s4.add_title("Experiment 1 should step pH chemistry at fixed total flow", "experiments to run")
    add_panel(
        s4,
        0.65,
        1.15,
        4.55,
        1.5,
        "Purpose",
        [
            "Excite pH_eq through the acid/acetate ratio.",
            "Hold total flow near 15 mL/min to reduce residence-time confounding.",
            "Use both upward and downward pH-coordinate changes.",
        ],
        COLORS["teal"],
        fill=COLORS["soft_teal"],
        body_size=10,
    )
    add_panel(
        s4,
        0.65,
        2.9,
        4.55,
        1.38,
        "Design equations",
        [
            "F_H + F_A = 10 mL/min, F_W = 5 mL/min.",
            "r = 10^(design_pH_eq - pKa).",
            "F_H = 10/(1+r), F_A = 10r/(1+r).",
        ],
        COLORS["maroon"],
        fill="FFFFFF",
        body_size=10,
    )
    rows = [
        ["design pH_eq", "F_H", "F_A", "F_W"],
        ["3.85", "8.90", "1.10", "5.00"],
        ["4.15", "8.03", "1.97", "5.00"],
        ["4.76", "5.00", "5.00", "5.00"],
        ["5.37", "1.97", "8.03", "5.00"],
        ["5.67", "1.10", "8.90", "5.00"],
    ]
    add_simple_table(s4, 5.75, 1.25, [1.65, 1.15, 1.15, 1.15], 0.46, rows, COLORS["maroon"], font_size=9.2)
    add_panel(
        s4,
        5.75,
        4.45,
        5.0,
        1.13,
        "Run order example",
        [
            "4.76 -> 4.15 -> 5.07 -> 3.85 -> 5.67 -> 4.45 -> 5.37 -> 4.76.",
            "Hold 10-20 min per step and sample PH_2 every 2-5 s if possible.",
        ],
        COLORS["blue"],
        fill=COLORS["soft_blue"],
        body_size=9.6,
    )
    add_panel(
        s4,
        0.65,
        5.12,
        4.55,
        0.72,
        "Validation output",
        [
            "Compare PH_2 against raw and affine equilibrium predictions for each held-out step.",
        ],
        COLORS["green"],
        fill=COLORS["soft_green"],
        body_size=10,
    )
    s4.add_footer(4)
    slides.append(s4)

    s5 = Slide("Experiment 2 should separate flow dynamics from chemistry")
    s5.add_background()
    s5.add_title("Experiment 2 should separate flow dynamics from chemistry", "experiments to run")
    add_panel(
        s5,
        0.62,
        1.15,
        3.7,
        1.62,
        "Block B: throughput",
        [
            "Keep composition fixed with equal streams.",
            "Run [3,3,3], [5,5,5], and [8,8,8] mL/min.",
            "Test whether response speed scales with total flow.",
        ],
        COLORS["blue"],
        fill=COLORS["soft_blue"],
        body_size=9.7,
    )
    add_panel(
        s5,
        4.62,
        1.15,
        3.7,
        1.62,
        "Block C: water fraction",
        [
            "Keep acid/acetate ratio fixed.",
            "Run [5,5,1], [5,5,5], and [5,5,10] mL/min.",
            "Separate dilution, conductivity, and flushing effects.",
        ],
        COLORS["teal"],
        fill=COLORS["soft_teal"],
        body_size=9.7,
    )
    add_panel(
        s5,
        8.62,
        1.15,
        3.7,
        1.62,
        "Block 0: local check",
        [
            "Start at [3,3,3].",
            "Step one pump to 6, return to baseline, then repeat.",
            "Use repeated center steps to expose drift.",
        ],
        COLORS["gold"],
        fill=COLORS["soft_gold"],
        body_size=9.7,
    )
    add_panel(
        s5,
        0.62,
        3.15,
        5.85,
        1.28,
        "Dynamic wrapper to fit after the data",
        [
            "tau_eff d y_hat/dt = y_static(t - theta) - y_hat.",
            "theta(t) = 60 V_delay / F_T(t), with F_T in mL/min.",
            "If data support it, split mixing lag from PH_2 sensor response.",
        ],
        COLORS["maroon"],
        fill="FFFFFF",
        body_size=10,
    )
    add_panel(
        s5,
        6.8,
        3.15,
        5.52,
        1.28,
        "Decision criteria",
        [
            "Improve test RMSE by at least 0.02 pH or 20 percent over static calibration.",
            "Hold final offsets mostly within 0.05-0.10 pH.",
            "Show physically sensible response speed versus total flow.",
        ],
        COLORS["green"],
        fill=COLORS["soft_green"],
        body_size=9.7,
    )
    add_panel(
        s5,
        0.62,
        5.02,
        11.7,
        0.82,
        "Boundary",
        [
            "No feedback control, MPC, RL, reward functions, or policies until this open-loop model predicts held-out PH_2 reliably.",
        ],
        COLORS["red"],
        fill=COLORS["soft_red"],
        body_size=11,
    )
    s5.add_footer(5)
    slides.append(s5)

    return slides


def write_pptx(slides: list[Slide]) -> None:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    created = xml_timestamp()

    with ZipFile(OUTPUT, "w", compression=ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", content_types_xml(slides))
        zf.writestr("_rels/.rels", package_rels_xml())
        zf.writestr("docProps/core.xml", core_xml(created))
        zf.writestr("docProps/app.xml", app_xml(len(slides)))
        zf.writestr("ppt/presentation.xml", presentation_xml(len(slides)))
        zf.writestr("ppt/_rels/presentation.xml.rels", presentation_rels_xml(len(slides)))
        zf.writestr("ppt/theme/theme1.xml", theme_xml())
        zf.writestr("ppt/slideMasters/slideMaster1.xml", slide_master_xml())
        zf.writestr("ppt/slideMasters/_rels/slideMaster1.xml.rels", slide_master_rels_xml())
        zf.writestr("ppt/slideLayouts/slideLayout1.xml", slide_layout_xml())
        zf.writestr("ppt/slideLayouts/_rels/slideLayout1.xml.rels", slide_layout_rels_xml())

        written_media: set[str] = set()
        for idx, slide in enumerate(slides, start=1):
            zf.writestr(f"ppt/slides/slide{idx}.xml", slide_xml(slide))
            zf.writestr(f"ppt/slides/_rels/slide{idx}.xml.rels", slide_rels_xml(slide))
            for image in slide.images:
                target = f"ppt/media/{image.media_name}"
                if target not in written_media:
                    zf.write(image.path, target)
                    written_media.add(target)


def validate_inputs() -> None:
    for path in [EQUILIBRIUM_SCATTER, BIOSMB_PLUMBING_MAP]:
        if not path.exists():
            raise FileNotFoundError(path)


def main() -> None:
    validate_inputs()
    slides = build_slides()
    if len(slides) > 5:
        raise ValueError(f"Deck has {len(slides)} slides, expected at most 5.")
    write_pptx(slides)
    print(f"Wrote {OUTPUT}")
    print(f"Slide count: {len(slides)}")


if __name__ == "__main__":
    main()
