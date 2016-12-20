'''OpenGL extension NV.texture_rectangle

Automatically generated by the get_gl_extensions script, do not edit!
'''
from OpenGL import platform, constants, constant, arrays
from OpenGL import extensions
from OpenGL.GL import glget
import ctypes
EXTENSION_NAME = 'GL_NV_texture_rectangle'
_DEPRECATED = False
GL_TEXTURE_RECTANGLE_NV = constant.Constant( 'GL_TEXTURE_RECTANGLE_NV', 0x84F5 )
glget.addGLGetConstant( GL_TEXTURE_RECTANGLE_NV, (1,) )
GL_TEXTURE_BINDING_RECTANGLE_NV = constant.Constant( 'GL_TEXTURE_BINDING_RECTANGLE_NV', 0x84F6 )
glget.addGLGetConstant( GL_TEXTURE_BINDING_RECTANGLE_NV, (1,) )
GL_PROXY_TEXTURE_RECTANGLE_NV = constant.Constant( 'GL_PROXY_TEXTURE_RECTANGLE_NV', 0x84F7 )
GL_MAX_RECTANGLE_TEXTURE_SIZE_NV = constant.Constant( 'GL_MAX_RECTANGLE_TEXTURE_SIZE_NV', 0x84F8 )
glget.addGLGetConstant( GL_MAX_RECTANGLE_TEXTURE_SIZE_NV, (1,) )


def glInitTextureRectangleNV():
    '''Return boolean indicating whether this extension is available'''
    return extensions.hasGLExtension( EXTENSION_NAME )
