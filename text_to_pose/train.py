import os

import pytorch_lightning as pl
from pytorch_lightning.callbacks import ModelCheckpoint
from pytorch_lightning.loggers import WandbLogger
from torch.utils.data import DataLoader

from text_to_pose.args import args
from text_to_pose.data import get_dataset
from text_to_pose.model import IterativeTextGuidedPoseGenerationModel
from text_to_pose.tests.tokenizer import DummyTokenizer
from text_to_pose.tokenizers.hamnosys.hamnosys_tokenizer import HamNoSysTokenizer
from text_to_pose.utils import zero_pad_collator

if __name__ == '__main__':
    os.environ["CUDA_VISIBLE_DEVICES"] = "0"

    if not args.no_wandb:
        logger = WandbLogger(project="text-to-pose", log_model=False, offline=False)
        if logger.experiment.sweep_id is None:
            logger.log_hyperparams(args)
    else:
        logger = None

    train_dataset = get_dataset(poses=args.pose, fps=args.fps, components=args.pose_components,
                                max_seq_size=args.max_seq_size, split="train[10:]")
    train_loader = DataLoader(train_dataset, batch_size=args.batch_size, shuffle=True, collate_fn=zero_pad_collator)

    validation_dataset = get_dataset(poses=args.pose, fps=args.fps, components=args.pose_components,
                                     max_seq_size=args.max_seq_size, split="train[:10]")
    validation_loader = DataLoader(validation_dataset, batch_size=args.batch_size, shuffle=True,
                                   collate_fn=zero_pad_collator)

    _, num_pose_joints, num_pose_dims = train_dataset[0]["pose"]["data"].shape

    # # Model Arguments
    # TODO parser.add_argument('--encoder_depth', type=int, default=2, help='number of layers for the encoder')
    # TODO parser.add_argument('--encoder_heads', type=int, default=4, help='number of heads for the encoder')

    model_args = dict(tokenizer=HamNoSysTokenizer(),
                      pose_dims=(num_pose_joints, num_pose_dims),
                      hidden_dim=args.hidden_dim,
                      max_seq_size=args.max_seq_size)

    # model = IterativeTextGuidedPoseGenerationModel.load_from_checkpoint(args.pred_checkpoint, **model_args)
    model = IterativeTextGuidedPoseGenerationModel(**model_args)

    callbacks = []
    if logger is not None:
        os.makedirs("models", exist_ok=True)
        os.makedirs("models/" + logger.experiment.id + "/", exist_ok=True)

        callbacks.append(ModelCheckpoint(
            filepath="models/" + logger.experiment.id + "/weights.ckpt",
            verbose=True,
            save_top_k=1,
            monitor='train_loss',
            mode='min'
        ))

    trainer = pl.Trainer(
        max_epochs=1000,
        logger=logger,
        callbacks=callbacks,
        gpus=args.gpus)

    trainer.fit(model, train_dataloader=train_loader, val_dataloaders=validation_loader)