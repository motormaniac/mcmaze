import { Application, Graphics, GraphicsContext } from "./node_modules/pixi.js/dist/pixi.mjs";

const TILE_SIZE = 64;
const GRID_WIDTH = 7;
const GRID_HEIGHT = 7;
const OFFSET = 100;
const OPEN_CHANCE = 0.15;
const HIDDEN_CHANCE = 0.1;
const HIDDEN_OPEN_CHANCE = 0.5; // when matching an open wall, what is the chance to generate hidden?
if (OPEN_CHANCE + HIDDEN_CHANCE > 1) {
  throw new Error("OPEN_CHANCE and HIDDEN_CHANCE must sum to 1 or less");
}
const DRAW_PHIDDEN = false; // whether to draw phidden walls differently from closed walls. In command blocks, both are represented as netherite_block, so this is purely for visualization purposes
const PHIDDEN_CLOSED_CHANCE = 0.3; // when matching a closed wall, what is the chance that it is a phidden instead
let stage = null;
let grid = [];

const TYPE = {
  OPEN:"open",
  CLOSED:"closed",
  HIDDEN:"hidden",
  PHIDDEN:"phidden"
}

class Grid {
  constructor(x, y,
    north = null,
    east = null,
    south = null,
    west = null) {
      this.x = x;
      this.y = y;
      this.north = north;
      this.east = east;
      this.south = south;
      this.west = west;
      this.enclosed = false; // if there are more than 2 walls
  }
  draw() {
    this.graphics = new Graphics();
    stage.addChild(this.graphics);
    this.graphics.strokeStyle = { width: 2, color: "black"}
    this.graphics
      .rect(-TILE_SIZE / 2, -TILE_SIZE / 2, TILE_SIZE, TILE_SIZE)
      .stroke("white");
    this.graphics.position.set(OFFSET + this.x * TILE_SIZE, OFFSET + this.y * TILE_SIZE);
    if (this.enclosed) {
      this.graphics
        .circle(0, 0, TILE_SIZE * 0.25)
        .fill("cyan");
    }
    this.drawWalls()
  }
  drawWalls() {
    if (this.north == TYPE.OPEN) {
      this.graphics
        .circle(0,-TILE_SIZE*0.5+5,5)
        .fill("red")
    } else if (this.north == TYPE.HIDDEN) {
      this.graphics
        .circle(0,-TILE_SIZE*0.5+5,5)
        .fill("blue")
    } else if (DRAW_PHIDDEN && this.north == TYPE.PHIDDEN) {
      this.graphics
        .circle(0,-TILE_SIZE*0.5+5,5)
        .fill("cyan")
    }
    
    if (this.east == TYPE.OPEN) {
      this.graphics
        .circle(TILE_SIZE*0.5-5,0,5)
        .fill("red")
    } else if (this.east == TYPE.HIDDEN) {
      this.graphics
        .circle(TILE_SIZE*0.5-5,0,5)
        .fill("blue")
    } else if (DRAW_PHIDDEN && this.east == TYPE.PHIDDEN) {
      this.graphics
        .circle(TILE_SIZE*0.5-5,0,5)
        .fill("cyan")
    }

    if (this.south == TYPE.OPEN) {
      this.graphics
        .circle(0,TILE_SIZE*0.5-5,5)
        .fill("red")
    } else if (this.south == TYPE.HIDDEN) {
      this.graphics
        .circle(0,TILE_SIZE*0.5-5,5)
        .fill("blue")
    } else if (DRAW_PHIDDEN && this.south == TYPE.PHIDDEN) {
      this.graphics
        .circle(0,TILE_SIZE*0.5-5,5)
        .fill("cyan")
    }

    if (this.west == TYPE.OPEN) {
      this.graphics
        .circle(-TILE_SIZE*0.5+5,0,5)
        .fill("red")
    } else if (this.west == TYPE.HIDDEN) {
      this.graphics
        .circle(-TILE_SIZE*0.5+5,0,5)
        .fill("blue")
    } else if (DRAW_PHIDDEN && this.west == TYPE.PHIDDEN) {
      this.graphics
        .circle(-TILE_SIZE*0.5+5,0,5)
        .fill("cyan")
    }
  }
}

function calculateGrid(x, y) {
  let gridCell = grid[x][y];
  let north = null;
  let east = null;
  let south = null;
  let west = null;

  let closedCount = 0;

  // write psuedocode similar to commandblocks

  if (y === 0) {
    north = TYPE.CLOSED;
    closedCount ++;
  } else if (grid[x][y-1].south !== null) {
    const otherCell = grid[x][y - 1];
    switch (otherCell.south) {
      case TYPE.OPEN:
        north = TYPE.OPEN;
        break;
      case TYPE.HIDDEN:
        north = TYPE.HIDDEN;
        break;
      // in command blocks, both closed and phidden are represented as netherite_block
      case TYPE.CLOSED:
      case TYPE.PHIDDEN:
        const rand = Math.random();
        north = rand <= PHIDDEN_CLOSED_CHANCE ? TYPE.CLOSED : TYPE.PHIDDEN;
        closedCount ++;
        break;
      default:
        throw new Error("Unexpected cell state: " + otherCell.south);
    }
  }

  if (x === GRID_WIDTH - 1) {
    east = TYPE.CLOSED;
    closedCount ++;
  } else if (grid[x+1][y].west !== null) {
    const otherCell = grid[x + 1][y];
    switch (otherCell.west) {
      case TYPE.OPEN:
        east = TYPE.OPEN;
        break;
      case TYPE.HIDDEN:
        east = TYPE.HIDDEN;
        break;
      // in command blocks, both closed and phidden are represented as netherite_block
      case TYPE.CLOSED:
      case TYPE.PHIDDEN:
        const rand = Math.random();
        east = rand <= PHIDDEN_CLOSED_CHANCE ? TYPE.CLOSED : TYPE.PHIDDEN;
        closedCount ++;
        break;
      default:
        throw new Error("Unexpected cell state: " + otherCell.west);
    }
  }

  if (y === GRID_HEIGHT - 1) {
    south = TYPE.CLOSED;
    closedCount ++;
  } else if (grid[x][y+1].north !== null) {
    const otherCell = grid[x][y + 1];
    switch (otherCell.north) {
      case TYPE.OPEN:
        south = TYPE.OPEN;
        break;
      case TYPE.HIDDEN:
        south = TYPE.HIDDEN;
        break;
      // in command blocks, both closed and phidden are represented as netherite_block
      case TYPE.CLOSED:
      case TYPE.PHIDDEN:
        const rand = Math.random();
        south = rand <= PHIDDEN_CLOSED_CHANCE ? TYPE.CLOSED : TYPE.PHIDDEN;
        closedCount ++;
        break;
      default:
        throw new Error("Unexpected cell state: " + otherCell.north);
    }
  }

  if (x === 0) {
    west = TYPE.CLOSED;
    closedCount ++;
  } else if (grid [x-1][y].east !== null) {
    const otherCell = grid[x - 1][y];
    switch (otherCell.east) {
      case TYPE.OPEN:
        west = TYPE.OPEN;
        break;
      case TYPE.HIDDEN:
        west = TYPE.HIDDEN;
        break;
      // in command blocks, both closed and phidden are represented as netherite_block
      case TYPE.CLOSED:
      case TYPE.PHIDDEN:
        const rand = Math.random();
        west = rand <= PHIDDEN_CLOSED_CHANCE ? TYPE.CLOSED : TYPE.PHIDDEN;
        closedCount ++;
        break;
      default:
        throw new Error("Unexpected cell state: " + otherCell.east);
    }
  }

  // Pick random new walls

  if (north === null) {
    const rand = Math.random();
    if (closedCount >= 2) {
      north = rand <= HIDDEN_OPEN_CHANCE ? TYPE.HIDDEN : TYPE.OPEN;
    } else if (closedCount < 2) {
      north = rand < OPEN_CHANCE
        ? TYPE.OPEN
        : (rand > 1 - HIDDEN_CHANCE ? TYPE.HIDDEN : TYPE.CLOSED);
      if (north === TYPE.CLOSED) {
        closedCount ++;
      }
    }
  }

  if (east === null) {
    const rand = Math.random();
    if (closedCount >= 2) {
      east = rand <= HIDDEN_OPEN_CHANCE ? TYPE.HIDDEN : TYPE.OPEN;
    } else if (closedCount < 2) {
      east = rand < OPEN_CHANCE
        ? TYPE.OPEN
        : (rand > 1 - HIDDEN_CHANCE ? TYPE.HIDDEN : TYPE.CLOSED);
      if (east === TYPE.CLOSED) {
        closedCount ++;
      }
    }
  }

  if (south === null) {
    const rand = Math.random();
    if (closedCount >= 2) {
      south = rand <= HIDDEN_OPEN_CHANCE ? TYPE.HIDDEN : TYPE.OPEN;
    } else if (closedCount < 2) {
      south = rand < OPEN_CHANCE
        ? TYPE.OPEN
        : (rand > 1 - HIDDEN_CHANCE ? TYPE.HIDDEN : TYPE.CLOSED);
      if (south === TYPE.CLOSED) {
        closedCount ++;
      }
    }
  }

  if (west === null) {
    const rand = Math.random();
    if (closedCount >= 2) {
      west = rand <= HIDDEN_OPEN_CHANCE ? TYPE.HIDDEN : TYPE.OPEN;
    } else if (closedCount < 2) {
      west = rand < OPEN_CHANCE
        ? TYPE.OPEN
        : (rand > 1 - HIDDEN_CHANCE ? TYPE.HIDDEN : TYPE.CLOSED);
      if (west === TYPE.CLOSED) {
        closedCount ++;
      }
    }
  }

  gridCell.north = north;
  gridCell.east = east;
  gridCell.south = south;
  gridCell.west = west;
  if (closedCount >= 3) {
    gridCell.enclosed = true;
  }
}

function iterateSpiral(callback) {
  let left = 0;
  let right = GRID_WIDTH - 1;
  let top = 0;
  let bottom = GRID_HEIGHT - 1;

  while (left <= right && top <= bottom) {
    for (let x = left; x <= right; x++) {
      callback(x, top);
    }
    top ++;

    for (let y = top; y <= bottom; y++) {
      callback(right, y);
    }
    right --;

    if (top <= bottom) {
      for (let x = right; x >= left; x--) {
        callback(x, bottom);
      }
      bottom --;
    }

    if (left <= right) {
      for (let y = bottom; y >= top; y--) {
        callback(left, y);
      }
      left ++;
    }
  }
}

(async () => {
  let app = new Application();
  console.log(app)
  await app.init({ background: '#000000ff', resizeTo: window });
  let canvas = app.canvas;
  canvas.classList.add('game-canvas');
  document.body.appendChild(canvas);

  stage = app.stage;

  grid = [];
  for (let x = 0; x < GRID_WIDTH; x++) {
    grid.push([]);
    for (let y = 0; y < GRID_HEIGHT; y++) {
      grid[x].push(new Grid(x, y));
    }
  }

  calculateGrid(0, 0);
  grid[0][0].draw();
  calculateGrid(0, GRID_HEIGHT - 1);
  grid[0][GRID_HEIGHT - 1].draw();
  calculateGrid(GRID_WIDTH - 1, 0);
  grid[GRID_WIDTH - 1][0].draw();
  calculateGrid(GRID_WIDTH - 1, GRID_HEIGHT - 1);
  grid[GRID_WIDTH - 1][GRID_HEIGHT - 1].draw();

  // draw all the cells
  iterateSpiral((x, y) => {
    calculateGrid(x, y);
    grid[x][y].draw();
  });
})()