class FXBuild:
  def __init__(self, name, index, fxcolor, bgcolor, speed, width,intensity ):
    self.name = name
    self.index = index
    self.fxcolor = fxcolor
    self.bgcolor = bgcolor
    self.speed = speed
    self.width = width
    self.intensity = intensity

  def calcWidth(self, noteCount):
    self.width = noteCount*12

