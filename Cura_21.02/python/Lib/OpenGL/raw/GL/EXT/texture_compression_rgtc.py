'''OpenGL extension EXT.texture_compression_rgtc

Automatically generated by the get_gl_extensions script, do not edit!
'''
from OpenGL import platform, constants, constant, arrays
from OpenGL import extensions
from OpenGL.GL import glget
import ctypes
EXTENSION_NAME = 'GL_EXT_texture_compression_rgtc'
_DEPRECATED = False
GL_COMPRESSED_RED_RGTC1_EXT = constant.Constant( 'GL_COMPRESSED_RED_RGTC1_EXT', 0x8DBB )
GL_COMPRESSED_SIGNED_RED_RGTC1_EXT = constant.Constant( 'GL_COMPRESSED_SIGNED_RED_RGTC1_EXT', 0x8DBC )
GL_COMPRESSED_RED_GREEN_RGTC2_EXT = constant.Constant( 'GL_COMPRESSED_RED_GREEN_RGTC2_EXT', 0x8DBD )
GL_COMPRESSED_SIGNED_RED_GREEN_RGTC2_EXT = constant.Constant( 'GL_COMPRESSED_SIGNED_RED_GREEN_RGTC2_EXT', 0x8DBE )


def glInitTextureCompressionRgtcEXT():
    '''Return boolean indicating whether this extension is available'''
    return extensions.hasGLExtension( EXTENSION_NAME )