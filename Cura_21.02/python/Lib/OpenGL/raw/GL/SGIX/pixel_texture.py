'''OpenGL extension SGIX.pixel_texture

Automatically generated by the get_gl_extensions script, do not edit!
'''
from OpenGL import platform, constants, constant, arrays
from OpenGL import extensions
from OpenGL.GL import glget
import ctypes
EXTENSION_NAME = 'GL_SGIX_pixel_texture'
_DEPRECATED = False
GL_PIXEL_TEX_GEN_SGIX = constant.Constant( 'GL_PIXEL_TEX_GEN_SGIX', 0x8139 )
GL_PIXEL_TEX_GEN_MODE_SGIX = constant.Constant( 'GL_PIXEL_TEX_GEN_MODE_SGIX', 0x832B )
glPixelTexGenSGIX = platform.createExtensionFunction( 
'glPixelTexGenSGIX',dll=platform.GL,
extension=EXTENSION_NAME,
resultType=None, 
argTypes=(constants.GLenum,),
doc='glPixelTexGenSGIX(GLenum(mode)) -> None',
argNames=('mode',),
deprecated=_DEPRECATED,
)


def glInitPixelTextureSGIX():
    '''Return boolean indicating whether this extension is available'''
    return extensions.hasGLExtension( EXTENSION_NAME )
