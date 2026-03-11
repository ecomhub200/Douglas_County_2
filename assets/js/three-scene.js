    (function() {
      const container = document.getElementById('canvas-container');
      const insightLabel = document.getElementById('insight-label');

      if (!container) return;

      // Track visibility for pausing rendering
      let isVizVisible = false;
      let threeLoaded = false;
      let animFrameId = null;

      const vizObserver = new IntersectionObserver(function(entries) {
        entries.forEach(function(entry) {
          isVizVisible = entry.isIntersecting;
          if (entry.isIntersecting && !threeLoaded) {
            threeLoaded = true;
            // Dynamically load Three.js CDN
            const script = document.createElement('script');
            script.src = 'https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js';
            script.onload = initThreeScene;
            document.head.appendChild(script);
          }
        });
      }, { rootMargin: '200px' });

      vizObserver.observe(container);

      function initThreeScene() {

      const scene = new THREE.Scene();

      const aspect = container.clientWidth / container.clientHeight;
      const frustumSize = 38;
      const camera = new THREE.OrthographicCamera(
        frustumSize * aspect / -2, frustumSize * aspect / 2,
        frustumSize / 2, frustumSize / -2, 0.1, 1000
      );

      let cameraAngle = Math.PI * 1.15;
      const cameraRadius = 48;
      const cameraHeight = 22;

      const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
      renderer.setSize(container.clientWidth, container.clientHeight);
      renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
      renderer.shadowMap.enabled = true;
      renderer.shadowMap.type = THREE.PCFSoftShadowMap;
      renderer.setClearColor(0x0f172a, 1);
      container.appendChild(renderer.domElement);

      const colors = {
        ground: 0x2d3a4d,
        road: 0x52525b,
        roadLine: 0xffffff,
        roadLineYellow: 0xfcd34d,
        sidewalk: 0xd6d3d1,
        sidewalkEdge: 0xa8a29e,
        building: 0x3d4a5c,
        buildingLight: 0x526078,
        buildingWindow: 0x60a5fa,
        tree: 0x22c55e,
        treeDark: 0x15803d,
        skin: 0xe8c4a0,
        fatal_K: 0xdc2626,
        seriousInjury_A: 0xea580c,
        minorInjury_B: 0xf59e0b,
        possibleInjury_C: 0x22c55e,
        pdo_O: 0x64748b,
        carColors: [0xdc2626, 0x2563eb, 0xf1f5f9, 0x1e293b, 0xfbbf24, 0x7c3aed, 0x0891b2, 0xf97316],
        signalPole: 0x27272a,
        signalBox: 0x18181b,
        signalRed: 0xef4444,
        signalYellow: 0xfbbf24,
        signalGreen: 0x22c55e
      };

      const roadWidth = 14;
      const laneWidth = 3.5;
      const intSize = roadWidth + 2;

      const signalLights = [];
      const pedestrians = [];
      const crosswalkPedestrians = { north: [], south: [], east: [], west: [] };
      const vehicles = [];

      // Ground
      const ground = new THREE.Mesh(
        new THREE.PlaneGeometry(160, 160),
        new THREE.MeshStandardMaterial({ color: colors.ground, roughness: 0.95 })
      );
      ground.rotation.x = -Math.PI / 2;
      ground.receiveShadow = true;
      scene.add(ground);

      // Roads
      function createRoadSegment(x, z, width, length, rotation = 0) {
        const g = new THREE.Group();

        const road = new THREE.Mesh(
          new THREE.PlaneGeometry(width, length),
          new THREE.MeshStandardMaterial({ color: colors.road, roughness: 0.75 })
        );
        road.rotation.x = -Math.PI / 2;
        road.position.y = 0.02;
        g.add(road);

        const swWidth = 3.5;
        const swHeight = 0.3;
        [-1, 1].forEach(side => {
          const sw = new THREE.Mesh(
            new THREE.BoxGeometry(swWidth, swHeight, length),
            new THREE.MeshStandardMaterial({ color: colors.sidewalk, roughness: 0.85 })
          );
          sw.position.set(side * (width / 2 + swWidth / 2), swHeight / 2, 0);
          sw.receiveShadow = true;
          sw.castShadow = true;
          g.add(sw);

          const curb = new THREE.Mesh(
            new THREE.BoxGeometry(0.15, swHeight + 0.05, length),
            new THREE.MeshStandardMaterial({ color: colors.sidewalkEdge, roughness: 0.9 })
          );
          curb.position.set(side * (width / 2 + 0.075), swHeight / 2, 0);
          g.add(curb);
        });

        [-0.12, 0.12].forEach(offset => {
          const yellowLine = new THREE.Mesh(
            new THREE.PlaneGeometry(0.15, length),
            new THREE.MeshStandardMaterial({ color: colors.roadLineYellow, roughness: 0.4 })
          );
          yellowLine.rotation.x = -Math.PI / 2;
          yellowLine.position.set(offset, 0.03, 0);
          g.add(yellowLine);
        });

        [-laneWidth, laneWidth].forEach(laneX => {
          for (let i = -length / 2 + 3; i < length / 2 - 3; i += 6) {
            const dash = new THREE.Mesh(
              new THREE.PlaneGeometry(0.15, 3),
              new THREE.MeshStandardMaterial({ color: colors.roadLine, roughness: 0.4 })
            );
            dash.rotation.x = -Math.PI / 2;
            dash.position.set(laneX, 0.03, i);
            g.add(dash);
          }
        });

        g.position.set(x, 0, z);
        g.rotation.y = rotation;
        return g;
      }

      scene.add(createRoadSegment(0, -28, roadWidth, 40, 0));
      scene.add(createRoadSegment(0, 28, roadWidth, 40, 0));
      scene.add(createRoadSegment(-28, 0, roadWidth, 40, Math.PI / 2));
      scene.add(createRoadSegment(28, 0, roadWidth, 40, Math.PI / 2));

      // Intersection
      const intersection = new THREE.Mesh(
        new THREE.PlaneGeometry(intSize, intSize),
        new THREE.MeshStandardMaterial({ color: colors.road, roughness: 0.75 })
      );
      intersection.rotation.x = -Math.PI / 2;
      intersection.position.y = 0.02;
      scene.add(intersection);

      const cornerSize = 3.5;
      [[-1, -1], [1, -1], [-1, 1], [1, 1]].forEach(([cx, cz]) => {
        const corner = new THREE.Mesh(
          new THREE.BoxGeometry(cornerSize, 0.3, cornerSize),
          new THREE.MeshStandardMaterial({ color: colors.sidewalk, roughness: 0.85 })
        );
        corner.position.set(cx * (intSize/2 + cornerSize/2), 0.15, cz * (intSize/2 + cornerSize/2));
        corner.receiveShadow = true;
        scene.add(corner);

        const ramp = new THREE.Mesh(
          new THREE.PlaneGeometry(1.2, 1.2),
          new THREE.MeshStandardMaterial({ color: 0xfbbf24, roughness: 0.7 })
        );
        ramp.rotation.x = -Math.PI / 2;
        ramp.position.set(cx * (intSize/2 + 0.8), 0.31, cz * (intSize/2 + 0.8));
        scene.add(ramp);
      });

      // Crosswalks
      function createCrosswalk(x, z, rotation, width = roadWidth - 1) {
        const cwGroup = new THREE.Group();
        const crosswalkDepth = 3.5;
        const barWidth = 0.6;
        const barSpacing = 1.0;

        [-crosswalkDepth/2, crosswalkDepth/2].forEach(offset => {
          const line = new THREE.Mesh(
            new THREE.PlaneGeometry(width, 0.25),
            new THREE.MeshStandardMaterial({ color: colors.roadLine, roughness: 0.35 })
          );
          line.rotation.x = -Math.PI / 2;
          line.position.set(0, 0.035, offset);
          cwGroup.add(line);
        });

        const numBars = Math.floor(width / barSpacing);
        for (let i = 0; i < numBars; i++) {
          const bar = new THREE.Mesh(
            new THREE.PlaneGeometry(barWidth, crosswalkDepth - 0.3),
            new THREE.MeshStandardMaterial({ color: colors.roadLine, roughness: 0.35 })
          );
          bar.rotation.x = -Math.PI / 2;
          bar.position.set(-width/2 + 0.5 + i * barSpacing, 0.035, 0);
          cwGroup.add(bar);
        }

        cwGroup.position.set(x, 0, z);
        cwGroup.rotation.y = rotation;
        return cwGroup;
      }

      const cwOffset = intSize / 2 + 2.5;
      scene.add(createCrosswalk(0, -cwOffset, 0));
      scene.add(createCrosswalk(0, cwOffset, 0));
      scene.add(createCrosswalk(-cwOffset, 0, Math.PI/2));
      scene.add(createCrosswalk(cwOffset, 0, Math.PI/2));

      // Stop Bars
      const stopBarOffset = cwOffset + 2.5;
      [
        { x: -laneWidth - 0.5, z: -stopBarOffset, r: 0 },
        { x: laneWidth + 0.5, z: stopBarOffset, r: 0 },
        { x: -stopBarOffset, z: laneWidth + 0.5, r: Math.PI/2 },
        { x: stopBarOffset, z: -laneWidth - 0.5, r: Math.PI/2 }
      ].forEach(sb => {
        const bar = new THREE.Mesh(
          new THREE.PlaneGeometry(laneWidth * 2 + 1, 0.6),
          new THREE.MeshStandardMaterial({ color: colors.roadLine, roughness: 0.35 })
        );
        bar.rotation.x = -Math.PI / 2;
        bar.rotation.z = sb.r;
        bar.position.set(sb.x, 0.035, sb.z);
        scene.add(bar);
      });

      // Traffic Signals
      function createTrafficSignal(x, z, facingAngle, direction) {
        const signalGroup = new THREE.Group();
        const poleHeight = 7;

        const pole = new THREE.Mesh(
          new THREE.CylinderGeometry(0.2, 0.25, poleHeight, 12),
          new THREE.MeshStandardMaterial({ color: colors.signalPole, roughness: 0.35, metalness: 0.6 })
        );
        pole.position.y = poleHeight / 2;
        pole.castShadow = true;
        signalGroup.add(pole);

        const armLength = 14;
        const arm = new THREE.Mesh(
          new THREE.CylinderGeometry(0.14, 0.16, armLength, 8),
          new THREE.MeshStandardMaterial({ color: colors.signalPole, roughness: 0.35, metalness: 0.6 })
        );
        arm.rotation.z = Math.PI / 2;
        arm.position.set(armLength / 2, poleHeight - 0.4, 0);
        signalGroup.add(arm);

        function createSignalHead(offsetX) {
          const headG = new THREE.Group();

          const bracket = new THREE.Mesh(
            new THREE.CylinderGeometry(0.07, 0.07, 0.6, 6),
            new THREE.MeshStandardMaterial({ color: colors.signalPole, roughness: 0.4 })
          );
          bracket.position.y = 0.3;
          headG.add(bracket);

          const backplate = new THREE.Mesh(
            new THREE.BoxGeometry(1.3, 2.4, 0.1),
            new THREE.MeshStandardMaterial({ color: 0x050505, roughness: 0.95 })
          );
          backplate.position.set(0, -0.85, 0.35);
          headG.add(backplate);

          const housing = new THREE.Mesh(
            new THREE.BoxGeometry(1.0, 2.1, 0.65),
            new THREE.MeshStandardMaterial({ color: colors.signalBox, roughness: 0.7 })
          );
          housing.position.y = -0.85;
          headG.add(housing);

          const lensData = [
            { color: colors.signalRed, y: -0.25, name: 'red' },
            { color: colors.signalYellow, y: -0.85, name: 'yellow' },
            { color: colors.signalGreen, y: -1.45, name: 'green' }
          ];

          const lensGroup = { red: null, yellow: null, green: null, direction: direction };

          lensData.forEach(lens => {
            const lensMesh = new THREE.Mesh(
              new THREE.CircleGeometry(0.25, 24),
              new THREE.MeshStandardMaterial({
                color: lens.color,
                emissive: 0x000000,
                emissiveIntensity: 0,
                roughness: 0.1
              })
            );
            lensMesh.rotation.y = Math.PI;
            lensMesh.position.set(0, lens.y, -0.33);
            headG.add(lensMesh);
            lensGroup[lens.name] = lensMesh;

            const visor = new THREE.Mesh(
              new THREE.BoxGeometry(0.6, 0.2, 0.4),
              new THREE.MeshStandardMaterial({ color: 0x050505, roughness: 0.9 })
            );
            visor.position.set(0, lens.y + 0.25, -0.52);
            headG.add(visor);
          });

          headG.position.set(offsetX, poleHeight - 0.4, 0);
          signalLights.push(lensGroup);
          return headG;
        }

        signalGroup.add(createSignalHead(armLength - 3));
        signalGroup.add(createSignalHead(armLength - 7));

        signalGroup.position.set(x, 0, z);
        signalGroup.rotation.y = facingAngle;
        return signalGroup;
      }

      const sigOffset = intSize / 2 + 5;
      scene.add(createTrafficSignal(sigOffset, -sigOffset, Math.PI, 'NB'));
      scene.add(createTrafficSignal(sigOffset, sigOffset, Math.PI/2, 'WB'));
      scene.add(createTrafficSignal(-sigOffset, sigOffset, 0, 'SB'));
      scene.add(createTrafficSignal(-sigOffset, -sigOffset, -Math.PI/2, 'EB'));

      // Vehicles
      function createVehicle(config) {
        const { x, z, direction, laneOffset, queuePosition, colorIdx } = config;
        const carGroup = new THREE.Group();
        const carColor = colors.carColors[colorIdx % colors.carColors.length];

        const carLength = 3.2;
        const carWidth = 1.4;

        const lowerBody = new THREE.Mesh(
          new THREE.BoxGeometry(carLength, 0.5, carWidth),
          new THREE.MeshStandardMaterial({ color: carColor, roughness: 0.25, metalness: 0.75 })
        );
        lowerBody.position.y = 0.45;
        lowerBody.castShadow = true;
        carGroup.add(lowerBody);

        const cabin = new THREE.Mesh(
          new THREE.BoxGeometry(carLength * 0.5, 0.5, carWidth - 0.15),
          new THREE.MeshStandardMaterial({ color: carColor, roughness: 0.25, metalness: 0.75 })
        );
        cabin.position.set(-carLength * 0.1, 0.95, 0);
        cabin.castShadow = true;
        carGroup.add(cabin);

        const windowMat = new THREE.MeshStandardMaterial({
          color: 0x1e3a5f, roughness: 0.05, metalness: 0.9, transparent: true, opacity: 0.8
        });

        const windshield = new THREE.Mesh(new THREE.PlaneGeometry(carWidth - 0.2, 0.45), windowMat);
        windshield.rotation.y = Math.PI / 2;
        windshield.rotation.z = -0.3;
        windshield.position.set(carLength * 0.15, 1.0, 0);
        carGroup.add(windshield);

        const rearWindow = new THREE.Mesh(new THREE.PlaneGeometry(carWidth - 0.25, 0.4), windowMat);
        rearWindow.rotation.y = -Math.PI / 2;
        rearWindow.rotation.z = 0.3;
        rearWindow.position.set(-carLength * 0.35, 0.98, 0);
        carGroup.add(rearWindow);

        [-carWidth/2 - 0.01, carWidth/2 + 0.01].forEach(zSide => {
          const sideWin = new THREE.Mesh(new THREE.PlaneGeometry(carLength * 0.4, 0.38), windowMat);
          sideWin.rotation.y = zSide > 0 ? 0 : Math.PI;
          sideWin.position.set(-carLength * 0.1, 0.98, zSide);
          carGroup.add(sideWin);
        });

        const wheelPositions = [
          [carLength * 0.35, 0.28, carWidth/2 + 0.05],
          [carLength * 0.35, 0.28, -carWidth/2 - 0.05],
          [-carLength * 0.35, 0.28, carWidth/2 + 0.05],
          [-carLength * 0.35, 0.28, -carWidth/2 - 0.05]
        ];
        wheelPositions.forEach(pos => {
          const tire = new THREE.Mesh(
            new THREE.CylinderGeometry(0.28, 0.28, 0.18, 18),
            new THREE.MeshStandardMaterial({ color: 0x1a1a1a, roughness: 0.9 })
          );
          tire.rotation.x = Math.PI / 2;
          tire.position.set(pos[0], pos[1], pos[2]);
          carGroup.add(tire);

          const rim = new THREE.Mesh(
            new THREE.CylinderGeometry(0.14, 0.14, 0.2, 12),
            new THREE.MeshStandardMaterial({ color: 0xa0a0a0, metalness: 0.85, roughness: 0.2 })
          );
          rim.rotation.x = Math.PI / 2;
          rim.position.set(pos[0], pos[1], pos[2]);
          carGroup.add(rim);
        });

        const hlMat = new THREE.MeshStandardMaterial({
          color: 0xfffef0, emissive: 0xfffef0, emissiveIntensity: 0.4
        });
        [-carWidth/2 + 0.2, carWidth/2 - 0.2].forEach(zp => {
          const hl = new THREE.Mesh(new THREE.BoxGeometry(0.08, 0.12, 0.2), hlMat);
          hl.position.set(carLength/2, 0.45, zp);
          carGroup.add(hl);
        });

        const brakeLightMat = new THREE.MeshStandardMaterial({
          color: 0xff2020, emissive: 0xff2020, emissiveIntensity: 0.8
        });
        const brakeLights = [];
        [-carWidth/2 + 0.18, carWidth/2 - 0.18].forEach(zp => {
          const bl = new THREE.Mesh(new THREE.BoxGeometry(0.08, 0.15, 0.25), brakeLightMat.clone());
          bl.position.set(-carLength/2, 0.48, zp);
          carGroup.add(bl);
          brakeLights.push(bl);
        });

        const grille = new THREE.Mesh(
          new THREE.PlaneGeometry(0.5, 0.2),
          new THREE.MeshStandardMaterial({ color: 0x1a1a1a, roughness: 0.8 })
        );
        grille.position.set(carLength/2 + 0.01, 0.38, 0);
        grille.rotation.y = Math.PI / 2;
        carGroup.add(grille);

        let posX, posZ, rotation;
        const stopDistance = stopBarOffset + 1.8;
        const queueSpacing = 4.5;

        const lane1Center = laneWidth / 2;
        const lane2Center = laneWidth * 1.5;

        switch(direction) {
          case 'NB':
            posX = -(laneOffset === 1 ? lane1Center : lane2Center);
            posZ = -(stopDistance + queuePosition * queueSpacing);
            rotation = Math.PI / 2;
            break;
          case 'SB':
            posX = (laneOffset === 1 ? lane1Center : lane2Center);
            posZ = stopDistance + queuePosition * queueSpacing;
            rotation = -Math.PI / 2;
            break;
          case 'EB':
            posX = -(stopDistance + queuePosition * queueSpacing);
            posZ = (laneOffset === 1 ? lane1Center : lane2Center);
            rotation = 0;
            break;
          case 'WB':
            posX = stopDistance + queuePosition * queueSpacing;
            posZ = -(laneOffset === 1 ? lane1Center : lane2Center);
            rotation = Math.PI;
            break;
        }

        carGroup.position.set(posX, 0, posZ);
        carGroup.rotation.y = rotation;

        const vehicleData = {
          mesh: carGroup,
          direction: direction,
          baseX: posX,
          baseZ: posZ,
          brakeLights: brakeLights,
          creepOffset: 0,
          velocity: 0
        };

        return vehicleData;
      }

      const vehicleConfigs = [
        { direction: 'NB', laneOffset: 1, queuePosition: 0, colorIdx: 0 },
        { direction: 'NB', laneOffset: 1, queuePosition: 1, colorIdx: 1 },
        { direction: 'NB', laneOffset: 2, queuePosition: 0, colorIdx: 4 },
        { direction: 'SB', laneOffset: 1, queuePosition: 0, colorIdx: 2 },
        { direction: 'SB', laneOffset: 1, queuePosition: 1, colorIdx: 3 },
        { direction: 'SB', laneOffset: 2, queuePosition: 0, colorIdx: 6 },
        { direction: 'EB', laneOffset: 1, queuePosition: 0, colorIdx: 7 },
        { direction: 'EB', laneOffset: 1, queuePosition: 1, colorIdx: 0 },
        { direction: 'EB', laneOffset: 2, queuePosition: 0, colorIdx: 1 },
        { direction: 'WB', laneOffset: 1, queuePosition: 0, colorIdx: 2 },
        { direction: 'WB', laneOffset: 1, queuePosition: 1, colorIdx: 3 },
        { direction: 'WB', laneOffset: 2, queuePosition: 0, colorIdx: 4 },
      ];

      vehicleConfigs.forEach(config => {
        const vehicle = createVehicle(config);
        vehicles.push(vehicle);
        scene.add(vehicle.mesh);
      });

      // Pedestrians
      function createPedestrian(x, z, rotation = 0, variant = 0) {
        const pedGroup = new THREE.Group();
        const shirtColors = [0x3b82f6, 0xef4444, 0x22c55e, 0xf59e0b, 0x8b5cf6, 0xec4899, 0x06b6d4, 0x84cc16];
        const pantsColors = [0x1e3a5f, 0x292524, 0x374151, 0x44403c];
        const shirtColor = shirtColors[variant % shirtColors.length];
        const pantsColor = pantsColors[variant % pantsColors.length];

        const head = new THREE.Mesh(
          new THREE.SphereGeometry(0.18, 14, 14),
          new THREE.MeshStandardMaterial({ color: colors.skin, roughness: 0.6 })
        );
        head.position.y = 1.25;
        head.castShadow = true;
        pedGroup.add(head);

        const torso = new THREE.Mesh(
          new THREE.CylinderGeometry(0.16, 0.18, 0.5, 8),
          new THREE.MeshStandardMaterial({ color: shirtColor, roughness: 0.7 })
        );
        torso.position.y = 0.85;
        torso.castShadow = true;
        pedGroup.add(torso);

        [-0.1, 0.1].forEach((side, i) => {
          const leg = new THREE.Mesh(
            new THREE.CylinderGeometry(0.07, 0.075, 0.55, 6),
            new THREE.MeshStandardMaterial({ color: pantsColor, roughness: 0.8 })
          );
          leg.position.set(side, 0.32, 0);
          leg.rotation.x = i === 0 ? -0.2 : 0.15;
          pedGroup.add(leg);
        });

        pedGroup.position.set(x, 0.3, z);
        pedGroup.rotation.y = rotation;
        pedGroup.scale.setScalar(1.1);
        return pedGroup;
      }

      // Sidewalk pedestrians
      [
        { x: -intSize/2 - 2.5, z: -intSize/2 - 2.5, r: Math.PI/4, v: 0 },
        { x: intSize/2 + 2.5, z: intSize/2 + 2.5, r: -Math.PI * 3/4, v: 1 },
        { x: -intSize/2 - 2.5, z: intSize/2 + 2.5, r: -Math.PI/4, v: 2 },
        { x: intSize/2 + 2.5, z: -intSize/2 - 2.5, r: Math.PI * 3/4, v: 3 },
      ].forEach(p => {
        const ped = createPedestrian(p.x, p.z, p.r, p.v);
        pedestrians.push({ mesh: ped, baseX: p.x, baseZ: p.z, onSidewalk: true });
        scene.add(ped);
      });

      // Crosswalk pedestrians
      const northPed = createPedestrian(-intSize/2 - 1, -cwOffset, Math.PI/2, 0);
      northPed.visible = false;
      crosswalkPedestrians.north.push(northPed);
      pedestrians.push({
        mesh: northPed,
        startX: -intSize/2 - 1,
        endX: intSize/2 + 1,
        fixedZ: -cwOffset,
        crosswalk: 'north',
        walkProgress: 0,
        axis: 'x'
      });
      scene.add(northPed);

      const southPed = createPedestrian(intSize/2 + 1, cwOffset, -Math.PI/2, 1);
      southPed.visible = false;
      crosswalkPedestrians.south.push(southPed);
      pedestrians.push({
        mesh: southPed,
        startX: intSize/2 + 1,
        endX: -intSize/2 - 1,
        fixedZ: cwOffset,
        crosswalk: 'south',
        walkProgress: 0,
        axis: 'x'
      });
      scene.add(southPed);

      const westPed = createPedestrian(-cwOffset, intSize/2 + 1, Math.PI, 2);
      westPed.visible = false;
      crosswalkPedestrians.west.push(westPed);
      pedestrians.push({
        mesh: westPed,
        startZ: intSize/2 + 1,
        endZ: -intSize/2 - 1,
        fixedX: -cwOffset,
        crosswalk: 'west',
        walkProgress: 0,
        axis: 'z'
      });
      scene.add(westPed);

      const eastPed = createPedestrian(cwOffset, -intSize/2 - 1, 0, 3);
      eastPed.visible = false;
      crosswalkPedestrians.east.push(eastPed);
      pedestrians.push({
        mesh: eastPed,
        startZ: -intSize/2 - 1,
        endZ: intSize/2 + 1,
        fixedX: cwOffset,
        crosswalk: 'east',
        walkProgress: 0,
        axis: 'z'
      });
      scene.add(eastPed);

      // Buildings
      function createBuilding(x, z, w, h, d, color = colors.building) {
        const g = new THREE.Group();
        const b = new THREE.Mesh(
          new THREE.BoxGeometry(w, h, d),
          new THREE.MeshStandardMaterial({ color, roughness: 0.7 })
        );
        b.position.y = h / 2;
        b.castShadow = true;
        b.receiveShadow = true;
        g.add(b);

        const windowMat = new THREE.MeshStandardMaterial({
          color: colors.buildingWindow, emissive: colors.buildingWindow, emissiveIntensity: 0.6
        });
        const rows = Math.floor(h / 2.2), cols = Math.floor(w / 2);
        for (let r = 0; r < rows; r++) {
          for (let c = 0; c < cols; c++) {
            const win = new THREE.Mesh(new THREE.PlaneGeometry(0.8, 1.1), windowMat);
            win.position.set(-w/2 + 1.2 + c * 2, 1.8 + r * 2.2, d/2 + 0.01);
            g.add(win);
          }
        }
        g.position.set(x, 0, z);
        return g;
      }

      [
        [-28, -28, 9, 16, 8], [-40, -22, 7, 11, 6, colors.buildingLight],
        [28, -28, 8, 18, 7], [40, -30, 6, 12, 5, colors.buildingLight],
        [-28, 28, 8, 14, 7], [-40, 24, 6, 9, 5, colors.buildingLight],
        [28, 28, 8, 15, 7], [40, 22, 6, 10, 5, colors.buildingLight],
      ].forEach(c => scene.add(createBuilding(...c)));

      // Trees
      function createTree(x, z, scale = 1) {
        const g = new THREE.Group();
        const trunk = new THREE.Mesh(
          new THREE.CylinderGeometry(0.18 * scale, 0.24 * scale, 1.2 * scale, 8),
          new THREE.MeshStandardMaterial({ color: 0x5d4037, roughness: 0.9 })
        );
        trunk.position.y = 0.6 * scale;
        trunk.castShadow = true;
        g.add(trunk);

        [1.0, 0.7, 0.45].forEach((size, i) => {
          const foliage = new THREE.Mesh(
            new THREE.ConeGeometry(0.9 * scale * size, 1.4 * scale, 8),
            new THREE.MeshStandardMaterial({ color: i % 2 === 0 ? colors.tree : colors.treeDark, roughness: 0.8 })
          );
          foliage.position.y = 1.4 * scale + i * 0.7 * scale;
          foliage.castShadow = true;
          g.add(foliage);
        });
        g.position.set(x, 0, z);
        return g;
      }

      const treePositions = [
        [-22, -22], [-26, -26], [-30, -22], [-22, -30], [-34, -34],
        [22, -22], [26, -26], [30, -22], [22, -30], [34, -34],
        [-22, 22], [-26, 26], [-30, 22], [-22, 30], [-34, 34],
        [22, 22], [26, 26], [30, 22], [22, 30], [34, 34],
        [35, -40], [40, -35], [42, -42], [38, -48], [45, -38],
        [48, -45], [35, -32], [32, -35], [28, -40], [40, -28],
        [35, 35], [40, 38], [38, 42], [42, 35], [45, 40],
        [32, 40], [40, 32], [48, 35], [35, 48], [42, 48],
        [-42, -42], [-38, -28], [-28, -38],
        [-38, 28], [-28, 38], [-42, 42],
        [38, 28], [28, 38],
      ];

      treePositions.forEach(([x, z]) => {
        const scale = 0.85 + Math.random() * 0.4;
        scene.add(createTree(x, z, scale));
      });

      // KABCO Crash Pins
      const pins = [];
      const pinData = [
        { x: 0, z: 0, color: colors.fatal_K, severity: 'K', delay: 0 },
        { x: 4, z: -3, color: colors.seriousInjury_A, severity: 'A', delay: 150 },
        { x: -3, z: 4, color: colors.seriousInjury_A, severity: 'A', delay: 200 },
        { x: -5, z: -2, color: colors.minorInjury_B, severity: 'B', delay: 300 },
        { x: 2, z: 5, color: colors.minorInjury_B, severity: 'B', delay: 350 },
        { x: -laneWidth, z: -20, color: colors.minorInjury_B, severity: 'B', delay: 600 },
        { x: 25, z: laneWidth, color: colors.minorInjury_B, severity: 'B', delay: 800 },
        { x: cwOffset - 1, z: 2, color: colors.possibleInjury_C, severity: 'C', delay: 400 },
        { x: -cwOffset + 1, z: -2, color: colors.possibleInjury_C, severity: 'C', delay: 450 },
        { x: laneWidth, z: 22, color: colors.possibleInjury_C, severity: 'C', delay: 700 },
        { x: -22, z: -laneWidth, color: colors.possibleInjury_C, severity: 'C', delay: 900 },
        { x: 0, z: -cwOffset + 1, color: colors.pdo_O, severity: 'O', delay: 500 },
        { x: 0, z: cwOffset - 1, color: colors.pdo_O, severity: 'O', delay: 550 },
        { x: laneWidth, z: -30, color: colors.pdo_O, severity: 'O', delay: 650 },
        { x: -laneWidth, z: 32, color: colors.pdo_O, severity: 'O', delay: 750 },
        { x: 35, z: 0, color: colors.pdo_O, severity: 'O', delay: 850 },
        { x: -38, z: laneWidth, color: colors.pdo_O, severity: 'O', delay: 950 },
      ];

      function createPin(x, z, color, severity, delay) {
        const g = new THREE.Group();

        const head = new THREE.Mesh(
          new THREE.SphereGeometry(0.5, 28, 28),
          new THREE.MeshStandardMaterial({
            color, roughness: 0.12, metalness: 0.5,
            emissive: color, emissiveIntensity: 0.85
          })
        );
        head.position.y = 2.2;
        head.castShadow = true;
        g.add(head);

        const stem = new THREE.Mesh(
          new THREE.CylinderGeometry(0.07, 0.1, 1.9, 12),
          new THREE.MeshStandardMaterial({ color: 0x374151, roughness: 0.3, metalness: 0.6 })
        );
        stem.position.y = 0.95;
        stem.castShadow = true;
        g.add(stem);

        const ring = new THREE.Mesh(
          new THREE.RingGeometry(0.4, 0.7, 36),
          new THREE.MeshBasicMaterial({ color, transparent: true, opacity: 0.75, side: THREE.DoubleSide })
        );
        ring.rotation.x = -Math.PI / 2;
        ring.position.y = 0.04;
        g.add(ring);

        g.position.set(x, 22, z);
        g.userData = { delay, baseY: 0, color, severity };
        return g;
      }

      pinData.forEach(d => {
        const pin = createPin(d.x, d.z, d.color, d.severity, d.delay);
        pins.push(pin);
        scene.add(pin);
      });

      // Lighting - Enhanced for better visibility
      scene.add(new THREE.AmbientLight(0x404060, 0.65));

      const dirLight = new THREE.DirectionalLight(0xffffff, 1.15);
      dirLight.position.set(30, 40, 25);
      dirLight.castShadow = true;
      dirLight.shadow.mapSize.width = 2048;
      dirLight.shadow.mapSize.height = 2048;
      dirLight.shadow.camera.near = 1;
      dirLight.shadow.camera.far = 150;
      dirLight.shadow.camera.left = -70;
      dirLight.shadow.camera.right = 70;
      dirLight.shadow.camera.top = 70;
      dirLight.shadow.camera.bottom = -70;
      dirLight.shadow.bias = -0.0002;
      scene.add(dirLight);

      // Fill light from opposite side to reduce harsh shadows
      const fillLight = new THREE.DirectionalLight(0xffffff, 0.35);
      fillLight.position.set(-25, 30, -20);
      scene.add(fillLight);

      scene.add(new THREE.PointLight(0x3b82f6, 0.5, 140));
      scene.add(new THREE.PointLight(0xfbbf24, 0.4, 120));

      // Signal Animation
      const phaseTiming = {
        'NS_GREEN': 6000,
        'NS_YELLOW': 2000,
        'EW_GREEN': 6000,
        'EW_YELLOW': 2000
      };

      const phaseSequence = ['NS_GREEN', 'NS_YELLOW', 'EW_GREEN', 'EW_YELLOW'];
      let phaseIndex = 0;
      let phaseStartTime = 0;
      let currentPhase = 'NS_GREEN';

      const insights = [
        "High Pedestrian Conflict Zone",
        "Red-Light Violation Risk",
        "Left-Turn Conflict Area",
        "Rear-End Crash Pattern"
      ];
      let lastInsightTime = 0;
      let insightIndex = 0;
      const INSIGHT_INTERVAL = 15000;
      const INSIGHT_DURATION = 3000;

      function updateSignals(phase) {
        currentPhase = phase;
        const isNSGreen = phase === 'NS_GREEN';
        const isNSYellow = phase === 'NS_YELLOW';
        const isEWGreen = phase === 'EW_GREEN';
        const isEWYellow = phase === 'EW_YELLOW';

        signalLights.forEach(lights => {
          const isNS = lights.direction === 'NB' || lights.direction === 'SB';

          ['red', 'yellow', 'green'].forEach(l => {
            lights[l].material.emissive.setHex(0x000000);
            lights[l].material.emissiveIntensity = 0;
          });

          if (isNS) {
            if (isNSGreen) {
              lights.green.material.emissive.setHex(colors.signalGreen);
              lights.green.material.emissiveIntensity = 2.0;
            } else if (isNSYellow) {
              lights.yellow.material.emissive.setHex(colors.signalYellow);
              lights.yellow.material.emissiveIntensity = 2.0;
            } else {
              lights.red.material.emissive.setHex(colors.signalRed);
              lights.red.material.emissiveIntensity = 2.0;
            }
          } else {
            if (isEWGreen) {
              lights.green.material.emissive.setHex(colors.signalGreen);
              lights.green.material.emissiveIntensity = 2.0;
            } else if (isEWYellow) {
              lights.yellow.material.emissive.setHex(colors.signalYellow);
              lights.yellow.material.emissiveIntensity = 2.0;
            } else {
              lights.red.material.emissive.setHex(colors.signalRed);
              lights.red.material.emissiveIntensity = 2.0;
            }
          }
        });

        const showNS = isNSGreen;
        const showEW = isEWGreen;

        crosswalkPedestrians.north.forEach(p => p.visible = showNS);
        crosswalkPedestrians.south.forEach(p => p.visible = showNS);
        crosswalkPedestrians.east.forEach(p => p.visible = showEW);
        crosswalkPedestrians.west.forEach(p => p.visible = showEW);

        pedestrians.forEach(p => {
          if (p.crosswalk) {
            const isNSCrosswalk = p.crosswalk === 'north' || p.crosswalk === 'south';
            if ((isNSCrosswalk && isNSGreen) || (!isNSCrosswalk && isEWGreen)) {
              p.walkProgress = 0;
            }
          }
        });
      }

      // Animation Loop
      let startTime = null;

      function easeOutBounce(x) {
        const n1 = 7.5625, d1 = 2.75;
        if (x < 1 / d1) return n1 * x * x;
        else if (x < 2 / d1) return n1 * (x -= 1.5 / d1) * x + 0.75;
        else if (x < 2.5 / d1) return n1 * (x -= 2.25 / d1) * x + 0.9375;
        return n1 * (x -= 2.625 / d1) * x + 0.984375;
      }

      function animate(time) {
        animFrameId = requestAnimationFrame(animate);

        // Skip rendering when section is off-screen
        if (!isVizVisible) return;

        if (!startTime) {
          startTime = time;
          phaseStartTime = time;
          lastInsightTime = time;
          updateSignals(phaseSequence[0]);
        }
        const elapsed = time - startTime;

        // Camera rotation (faster orbit)
        cameraAngle += 0.0009;
        camera.position.x = Math.cos(cameraAngle) * cameraRadius;
        camera.position.z = Math.sin(cameraAngle) * cameraRadius;
        camera.position.y = cameraHeight + Math.sin(cameraAngle * 0.3) * 2;
        camera.lookAt(0, 0, 0);

        // Signal phase cycling
        const currentPhaseDuration = phaseTiming[phaseSequence[phaseIndex]];
        if (time - phaseStartTime > currentPhaseDuration) {
          phaseStartTime = time;
          phaseIndex = (phaseIndex + 1) % phaseSequence.length;
          updateSignals(phaseSequence[phaseIndex]);
        }

        // Insight moments
        if (time - lastInsightTime > INSIGHT_INTERVAL) {
          insightLabel.textContent = insights[insightIndex];
          insightLabel.classList.add('visible');

          pins.forEach(pin => {
            const head = pin.children[0];
            if (head) head.material.emissiveIntensity = 1.5;
          });

          setTimeout(() => {
            insightLabel.classList.remove('visible');
            pins.forEach(pin => {
              const head = pin.children[0];
              if (head) head.material.emissiveIntensity = 0.85;
            });
          }, INSIGHT_DURATION);

          lastInsightTime = time;
          insightIndex = (insightIndex + 1) % insights.length;
        }

        // Vehicle animations
        vehicles.forEach(vehicle => {
          const isNS = vehicle.direction === 'NB' || vehicle.direction === 'SB';
          const isGreen = (isNS && currentPhase === 'NS_GREEN') || (!isNS && currentPhase === 'EW_GREEN');
          const isYellow = (isNS && currentPhase === 'NS_YELLOW') || (!isNS && currentPhase === 'EW_YELLOW');
          const isRed = !isGreen && !isYellow;

          vehicle.brakeLights.forEach(bl => {
            bl.material.emissiveIntensity = isRed ? 1.0 : (isYellow ? 0.6 : 0.15);
          });

          if (isGreen) {
            vehicle.velocity = Math.min(vehicle.velocity + 0.0005, 0.015);
            vehicle.creepOffset = Math.min(vehicle.creepOffset + vehicle.velocity, 0.5);
          } else if (isYellow) {
            vehicle.velocity = Math.max(vehicle.velocity - 0.001, 0);
            vehicle.creepOffset = Math.min(vehicle.creepOffset + vehicle.velocity, 0.5);
          } else {
            vehicle.velocity = 0;
            vehicle.creepOffset = Math.max(vehicle.creepOffset - 0.02, 0);
          }

          switch(vehicle.direction) {
            case 'NB':
              vehicle.mesh.position.z = vehicle.baseZ + vehicle.creepOffset;
              break;
            case 'SB':
              vehicle.mesh.position.z = vehicle.baseZ - vehicle.creepOffset;
              break;
            case 'EB':
              vehicle.mesh.position.x = vehicle.baseX + vehicle.creepOffset;
              break;
            case 'WB':
              vehicle.mesh.position.x = vehicle.baseX - vehicle.creepOffset;
              break;
          }
        });

        // Pin animations
        pins.forEach((pin, i) => {
          if (elapsed > pin.userData.delay) {
            const pe = elapsed - pin.userData.delay;
            const dur = 1000;

            if (pe < dur) {
              pin.position.y = 22 - 22 * easeOutBounce(pe / dur);
            } else {
              const ft = (pe - dur) / 1000;
              const pulseSpeed = 1.2 + (i % 3) * 0.2;
              pin.position.y = pin.userData.baseY + Math.sin(ft * pulseSpeed) * 0.05;

              const ring = pin.children[2];
              if (ring) {
                ring.material.opacity = 0.4 + Math.sin(ft * pulseSpeed) * 0.2;
                ring.scale.setScalar(1 + Math.sin(ft * pulseSpeed) * 0.1);
              }
            }
          }
        });

        // Pedestrian animation
        pedestrians.forEach((p, i) => {
          if (p.onSidewalk) {
            const t = elapsed * 0.0002 + i * 1.2;
            p.mesh.position.x = p.baseX + Math.sin(t) * 0.08;
            p.mesh.position.z = p.baseZ + Math.cos(t * 0.9) * 0.06;
          } else if (p.crosswalk && p.mesh.visible) {
            p.walkProgress += 0.003;

            if (p.walkProgress > 1) {
              p.walkProgress = 1;
            }

            if (p.axis === 'x') {
              const newX = p.startX + (p.endX - p.startX) * p.walkProgress;
              p.mesh.position.x = newX;
              p.mesh.position.z = p.fixedZ;
            } else {
              const newZ = p.startZ + (p.endZ - p.startZ) * p.walkProgress;
              p.mesh.position.z = newZ;
              p.mesh.position.x = p.fixedX;
            }
          }
        });

        renderer.render(scene, camera);
      }

      animate(0);

      window.addEventListener('resize', () => {
        if (!renderer) return;
        const aspect = container.clientWidth / container.clientHeight;
        camera.left = frustumSize * aspect / -2;
        camera.right = frustumSize * aspect / 2;
        camera.updateProjectionMatrix();
        renderer.setSize(container.clientWidth, container.clientHeight);
      });

      } // end initThreeScene
    })();
