# -*- coding: utf-8 -*-
import os
import re
import algorithms
from lxml import etree
from kitchen.text.converters import to_unicode, to_bytes
from PIL import Image, ImageDraw

# Useful xpath queries for selecting items with bboxes from hocr.
ALL_BBOXES = u"//*[@title]"
PAGES = u"//*[@class='ocr_page' and @title]"
LINES = u"//*[@class='ocr_line' and @title]"
WORDS = u"//*[@class='ocr_word' and @title]" #Returns a list
XWORDS = u"//*[@class='ocrx_word' and @title]" #Returns a list


class HocrContext(object):
    """
    A context manager for working with parsed hocr.
    """
    def __init__(self, hocrfilepath):
        super(HocrContext, self).__init__()
        self.hocrfilepath = hocrfilepath

    def __enter__(self):
        abspath = os.path.abspath(os.path.expanduser(self.hocrfilepath))
        with open(abspath) as hocrfile:
            self.parsedhocr = etree.parse(hocrfile)
            return self.parsedhocr


    def __exit__(self, type, value, traceback):
        del self.parsedhocr
        return False    # No exception suppression.
        # self.cr.restore()

def extract_words(context):
    """
    Extract all hocr words. Return a list of 2 tuples containing the
    word, and an absolute xpath to locate it in the given hocr document.
    """
    # words = [(e.text, context.getpath(e)) for e in context.xpath(WORDS)]
    words = []
    for e in context.xpath(WORDS):
        word = (to_unicode(e.text), context.getpath(e).decode(u'utf-8'))
        words.append(word)
    return words


def extract_hocr_tokens(hocr_file):
    """
    Extracts all the nonempty words in an hOCR file and returns them
    as a list.
    """
    words = []
    context = etree.iterparse(hocr_file, events=('end',), tag='span', html=True)
    for event, element in context:
        # Strip extraneous newlines generated by the ocr_line span tags.
        if element.text is not None:
            word = to_unicode(element.text.rstrip())
        if len(word) > 0:
            words.append(word)
        element.clear()
        while element.getprevious() is not None:
            del element.getparent()[0]
    del context
    return words

@algorithms.unibarrier
def extract_suggestions(context, wordxpath):
    """
    Extract the suggestions for the given word identified by wordxpath.
    Returns a list of tuples of the form (text_of_suggestion, nlpnum).
    """
    word_element = context.xpath(wordxpath)[0]
    suggestion_tags = word_element.getchildren()[0].getchildren()
    return [(algorithms.sanitize(tag.text), float(tag.attrib[u'title'][4:])) for tag in suggestion_tags]

@algorithms.unibarrier
def insert_suggestions(con, wordxpath, suggestions):
    """
    Add a hocr alternative tag to the specified word
    in the specified document. We assume "correctness" 
    in that the specified word should be encoded as either:
    a. the text of the element that wordxpath refers to, or
    b. that element has no text, but rather a span element of class
       "alternatives", which contains ins tags representing each
       suggestion.
    Suggestions is a list of tuples of the form
    (suggested unicode word, nlpnum).
    """
    word_span_element = con.xpath(wordxpath)[0] #The span tag representing the hocr word
    suggestion_span = None
    if algorithms.sanitize(word_span_element.text) != u'':
        oldtext = word_span_element.text
        word_span_element.text = u''
        suggestion_span = etree.Element(u'span', {u'class':u'alternatives'})
        word_span_element.append(suggestion_span)
    else:
        suggestion_span = word_span_element.getchildren()[0]
    for s in suggestions:
        ins = etree.Element(u'ins', {u'class':u'alt', u'title':u'nlp '+unicode(s[1])})
        ins.text = s[0]
        suggestion_span.append(ins)

@algorithms.unibarrier
def insert_suggestion(con, wordxpath, suggestion, nlpnum):
    insert_suggestions(con, wordxpath, [(suggestion, nlpnum)])

def extract_bboxes(hocr_file, xpaths=[ALL_BBOXES]):
    """
    Extracts a list of bboxes as 4-tuples, in the same order that they
    appear in the hocr file. BBoxes are only extracted from those
    elements matching the specified xpath bboxes.
    """
    context = etree.parse(hocr_file)
    bboxpattern = r'.*(bbox{1} [0-9]+ [0-9]+ [0-9]+ [0-9]+)'
    results = {}
    for xpath in xpaths:
        bboxes = []
        for e in context.xpath(xpath):
            match = re.match(bboxpattern, e.attrib[u'title'])
            bbox = tuple(map(int, match.groups()[0][5:].split(u' ')))
            bboxes.append(bbox)
        results[xpath] = bboxes

    return results

def drawbboxes(bboxes, pil_img, color='blue'):
    """
    Draw all bboxes in the specified color. Returnss a
    """
    draw = ImageDraw.Draw(pil_img)
    for bbox in bboxes:
        draw.rectangle(((bbox[0], bbox[1]),(bbox[2], bbox[3])), outline=color)
    del draw
    return pil_img

def previewbboxs(imgfile, hocrfile, color='blue'):
    """
    Display a preview of the specified image with the bboxes from the
    hocr file drawn on it.
    """
    opened = Image.open(imgfile)
    drawbboxes(extract_bboxes(hocrfile)[ALL_BBOXES], opened, color)
    opened.show()

def markbboxes(imgfile, hocrfile, tag_color_dict):
    """
    Draw all the bboxes of the specified hocr class with the specified
    colors. Returns a PIL image file. Tag_color_dict is a dictionary of the
    form {'hocrclass':'color'}.
    """
    # bboxesperclass = extract_bboxes_by_classes(hocrfile, tag_color_dict.keys())
    bboxesperclass = extract_bboxes(hocrfile, tag_color_dict.keys())
    pil_img = Image.open(imgfile)
    for hocr_class, bboxlist in bboxesperclass.iteritems():
        drawbboxes(bboxlist, pil_img, tag_color_dict[hocr_class])

    pil_img.show()
    return pil_img

# def detect_word_lang(hocrfile, uni_blocks, threshold=1.0):

# if __name__ == '__main__':
