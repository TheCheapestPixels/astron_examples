# For UberDOGs
from direct.distributed.DistributedObjectGlobal import DistributedObjectGlobal
from direct.distributed.DistributedObjectGlobalAI import DistributedObjectGlobalAI
from direct.distributed.DistributedObjectGlobalUD import DistributedObjectGlobalUD
# For regular DOs
from direct.distributed.DistributedObject import DistributedObject
from direct.distributed.DistributedObjectAI import DistributedObjectAI
from direct.distributed.DistributedObjectUD import DistributedObjectUD
from direct.distributed.DistributedObjectOV import DistributedObjectOV
# For DOs that are also Panda3D scene graph nodes
from direct.distributed.DistributedNode import DistributedNode
from direct.distributed.DistributedNodeAI import DistributedNodeAI
# Assembling messages
from direct.distributed.PyDatagram import PyDatagram
from direct.distributed import MsgTypes
from direct.distributed.AstronInternalRepository import AstronInternalRepository
# AI tasks
from direct.task import Task

# Constant DO and channel IDs
from simple_example_globals import LoginManagerId

# Game settings
avatar_speed = 100.0
avatar_rotation_speed = 20.0 * 360.0

# LoginManager
# * Authenticates Client
# * Makes DistributedMaproot set up and create an avatar

class LoginManager(DistributedObjectGlobal):
    def login(self, username, password):
        # FIXME: Use TLS so that these are encrypted!
        self.sendUpdate("login", [username, password])

class LoginManagerAI(DistributedObjectGlobalAI):
    def set_maproot(self, maproot_doId):
        self.sendUpdate("set_maproot", [maproot_doId])

class LoginManagerUD(DistributedObjectGlobalUD):
    def set_maproot(self, maproot_doId):
        """Tells the LoginManagerUD what maproot to notify on login."""
        
        self.maproot = DistributedMaprootUD(self.air)
        self.maproot.generateWithRequiredAndId(maproot_doId, 0, 1)

    def login(self, username, password):
        clientId = self.air.get_msg_sender()
        if (username == "guest") and (password == "guest"):
            # Authenticate a client
            # FIXME: "2" is the magic number for CLIENT_STATE_ESTABLISHED,
            # for which currently no mapping exists.
            self.air.setClientState(clientId, 2)

            # The client is now authenticated; create an Avatar
            self.maproot.sendUpdate("createAvatar", # Field to call
                                    [clientId])     # Arguments
            
            # log login
            self.notify.info("Login successful (user: %s)" % (username,))

        else:
            # Disconnect for bad auth
            # FIXME: "122" is the magic number for login problems.
            # See https://github.com/Astron/Astron/blob/master/doc/protocol/10-client.md
            self.air.eject(clientId, 122, "Bad credentials")
            
            # log login attempt
            self.notify.info("Ejecting client for bad credentials (user: %s)" % (username,))

#
# DistributedMaproot
# * has all avatars in its zone 0
# * generates new avatars
#

class DistributedMaproot(DistributedObject):
    pass
    
class DistributedMaprootOV(DistributedObjectOV):
    pass

class DistributedMaprootAI(DistributedObjectAI):
    def generate(self):
        pass
    
    def createAvatar(self, clientId):
        # Create the avatar
        avatar = DistributedAvatarAI(self.air)
        avatar.generateWithRequiredAndId(self.air.allocateChannel(), self.getDoId(), 0) # random doId, parentId, zoneId
        # Set the client to be interested in our zone 0. He can't do
        # that himself (or rather: shouldn't be allowed to) as he has
        # no visibility of this object.
        self.air.clientAddInterest(clientId, 0, self.getDoId(), 0) # client, interest, parent, zone
        # Set its owner to the client, upon which in the Clients repo
        # magically OV (OwnerView) is generated.
        self.air.setOwner(avatar.getDoId(), clientId)
        # Declare this to be a session object.
        self.air.clientAddSessionObject(clientId, self.getDoId())

# The UberDOG needs this. FIXME: Or maybe just the DC reader because of /UD in .dc?
class DistributedMaprootUD(DistributedObjectUD):
    pass

#
# DistributedAvatar
#

class DistributedAvatar(DistributedNode):
    def generateInit(self):
        model = base.loader.loadModel("models/smiley")
        model.reparent_to(self)
        model.setH(180.0)
        # Signal app that this is its avatar
        base.messenger.send("distributed_avatar", [self])
        
    def setXYZH(self, *args):
        DistributedNode.setXYZH(self, *args)
        
    def delete(self):
        print("Avatar got removed.")

class DistributedAvatarOV(DistributedObjectOV):
    def generateInit(self):
        # Make yourself known to the client
        base.messenger.send("avatar", [self])
        
    def indicateIntent(self, heading, speed):
        self.sendUpdate("indicateIntent", [heading, speed])

class DistributedAvatarAI(DistributedNodeAI):
    def generate(self, repository=None):
        self.heading = 0.0
        self.speed = 0.0
        self.update_task = base.taskMgr.add(self.update_position, "Avatar position update")

    def delete(self):
        base.taskMgr.remove(self.update_task)

    def indicateIntent(self, heading, speed):
        if (heading < -1.0) or (heading > 1.0) or (speed < -1.0) or (speed > 1.0):
            # Client is cheating!
            # FIXME: Eject client
            return
        self.heading = heading
        self.speed = speed
    
    def update_position(self, task):
        if (self.heading != 0.0) or (self.speed != 0.0):
            dt = task.getDt()
            self.setH((self.getH() + self.heading * avatar_rotation_speed * dt) % 360.0)
            self.setY(self, self.speed * avatar_speed * dt)
            if self.getX() < -10.0:
                self.setX(-10.0)
            if self.getX() > 10.0:
                self.setX(10.0)
            if self.getY() < -10.0:
                self.setY(-10.0)
            if self.getY() > 10.0:
                self.setY(10.0)
            self.b_setXYZH(self.getX(), self.getY(), self.getZ(), self.getH())
        return Task.cont
