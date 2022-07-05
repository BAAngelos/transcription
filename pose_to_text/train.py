import os

import pytorch_lightning as pl
from pytorch_lightning.callbacks import ModelCheckpoint
from pytorch_lightning.loggers import WandbLogger
from torch.utils.data import DataLoader

from ..shared.collator import zero_pad_collator
from ..shared.tokenizers.sign_language_tokenizer import SignLanguageTokenizer
from ..text_to_pose.args import args
from .data import get_dataset
from .model import PoseToTextModel

if __name__ == '__main__':
    LOGGER = None
    if not args.no_wandb:
        LOGGER = WandbLogger(project="pose-to-text", log_model=False, offline=False)
        if LOGGER.experiment.sweep_id is None:
            LOGGER.log_hyperparams(args)

    train_dataset = get_dataset(poses=args.pose, fps=args.fps, components=args.pose_components,
                                max_seq_size=args.max_seq_size, split="train[:10]")
    train_loader = DataLoader(train_dataset, batch_size=args.batch_size,
                              shuffle=True, collate_fn=zero_pad_collator)

    validation_dataset = get_dataset(poses=args.pose, fps=args.fps, components=args.pose_components,
                                     max_seq_size=args.max_seq_size, split="train[:10]")
    validation_loader = DataLoader(validation_dataset, batch_size=args.batch_size, collate_fn=zero_pad_collator)

    _, num_pose_joints, num_pose_dims = train_dataset[0]["pose"]["data"].shape

    # Model Arguments
    model_args = dict(tokenizer=SignLanguageTokenizer(),
                      pose_dims=(num_pose_joints, num_pose_dims),
                      hidden_dim=args.hidden_dim,
                      text_encoder_depth=args.text_encoder_depth,
                      pose_encoder_depth=args.pose_encoder_depth,
                      encoder_heads=args.encoder_heads,
                      max_seq_size=args.max_seq_size,
                      max_decode_seq_size=30)

    if args.checkpoint is not None:
        model = PoseToTextModel.load_from_checkpoint(args.checkpoint, **model_args)
    else:
        model = PoseToTextModel(**model_args)

    callbacks = []
    if LOGGER is not None:
        os.makedirs("models", exist_ok=True)

        callbacks.append(ModelCheckpoint(
            dirpath="models/" + LOGGER.experiment.id,
            filename="model",
            verbose=True,
            save_top_k=1,
            monitor='train_loss',
            mode='min'
        ))

    trainer = pl.Trainer(
        max_epochs=5000,
        check_val_every_n_epoch=10,  # validation is really slow
        logger=LOGGER,
        callbacks=callbacks,
        gpus=args.gpus)

    trainer.fit(model, train_dataloaders=train_loader, val_dataloaders=validation_loader)
